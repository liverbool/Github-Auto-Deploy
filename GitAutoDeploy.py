#!/usr/bin/env python

import json, urlparse, sys, os
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from subprocess import call

class GitAutoDeploy(BaseHTTPRequestHandler):
    cdir = os.path.dirname(os.path.realpath(__file__))
    CONFIG_FILEPATH = cdir + '/GitAutoDeploy.conf.json'
    CONFIG_PID_FILE = cdir + '/.pid'
    config = None
    quiet = False
    daemon = False
    stop = False

    @classmethod
    def getConfig(myClass):
        if(myClass.config == None):
            try:
                configString = open(myClass.CONFIG_FILEPATH).read()
            except:
                sys.exit('Could not load ' + myClass.CONFIG_FILEPATH + ' file')

            try:
                myClass.config = json.loads(configString)
            except:
                sys.exit(myClass.CONFIG_FILEPATH + ' file is not valid json')

            for repository in myClass.config['repositories']:
                if(not os.path.isdir(repository['path'])):
                    sys.exit('Directory ' + repository['path'] + ' not found')
                # Check for a repository with a local or a remote GIT_WORK_DIR
                if not os.path.isdir(os.path.join(repository['path'], '.git')) \
                   and not os.path.isdir(os.path.join(repository['path'], 'objects')):
                    sys.exit('Directory ' + repository['path'] + ' is not a Git repository')

        return myClass.config

    def do_POST(self):
        if self.headers.getheader('x-github-event') != 'push':
            if not self.quiet:
                print 'We only handle push events'
            self.respond(304)
            return

        self.respond(204)

        urls = self.parseRequest()
        for url in urls:
            if not self.quiet:
            	print 'Matching url: ' + url
            	
            paths = self.getMatchingPaths(url)
            for path in paths:
                self.fetch(path)
                self.deploy(path)

    def parseRequest(self):
        length = int(self.headers.getheader('content-length'))
        body = self.rfile.read(length)
        payload = json.loads(body)
        self.branch = payload['ref']
        return [payload['repository']['url']]

    def getMatchingPaths(self, repoUrl):
        res = []
        config = self.getConfig()
        for repository in config['repositories']:
            if(repository['url'] == repoUrl):
                res.append(repository['path'])
        return res

    def respond(self, code):
        self.send_response(code)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()

    def fetch(self, path):
        if(not self.quiet):
            print "\nPost push request received"
            print 'Updating ' + path
            call(['cd "' + path + '" && git fetch'], shell=True, stdout=sys.stdout, stderr=sys.stderr)
        else:
            call(['cd "' + path + '" && git fetch'], shell=True)

    def deploy(self, path):
        config = self.getConfig()
        for repository in config['repositories']:
            if(repository['path'] == path):
                if 'deploy' in repository:
                    branch = None
                    if 'branch' in repository:
                        branch = repository['branch']
		    
		    if(not self.quiet):
		        print 'Branch: ' + str(branch)
		        print 'self.Branch: ' + str(self.branch)
		        
		    cmd = 'cd "' + path + '" && ' + repository['deploy']
		    
                    if branch is None or branch == self.branch:
                        if(not self.quiet):
                            print 'Executing deploy command'
                            print cmd
                            call([cmd], shell=True, stdout=sys.stdout, stderr=sys.stderr)
                        else:
                            call([cmd], shell=True)
                        
                    elif not self.quiet:
                        print 'Push to different branch (%s != %s), not deploying' % (branch, self.branch)
                break

def main():
    try:
        server = None
        pid_file = GitAutoDeploy.CONFIG_PID_FILE
        
        for arg in sys.argv: 
            if(arg == '-d' or arg == '--daemon-mode'):
                GitAutoDeploy.daemon = True
                GitAutoDeploy.quiet = True
                
            if(arg == '-q' or arg == '--quiet'):
                GitAutoDeploy.quiet = True
                
            if(arg == '--stop'):
            	GitAutoDeploy.stop = True
                
        if (GitAutoDeploy.stop):
            print 'Stoping ...'
            
            if(not server is None):
            	server.socket.close()

	    if (os.path.exists(pid_file)):
	        call(['kill ' + open(pid_file, 'r').read()], shell=True)
                os.remove(pid_file)

            sys.exit('Goodbye')
            return
        
        # check process file exist with no real process (stoped with other)
        # remove it
        if (os.path.exists(pid_file)):
            try:
                os.kill(open(pid_file, 'r').read(), 0)
                print 'Process is running...'
                return
            except (OSError) as ex:
            	os.remove(pid_file)
        	
        if(GitAutoDeploy.daemon):
            pid = os.fork()
            if(pid != 0):
                sys.exit()
            os.setsid()

        if(not GitAutoDeploy.quiet):
            print 'Github Autodeploy Service v0.2 started'
        else:
            print 'Github Autodeploy Service v 0.2 started at PID %s in daemon mode' % (os.getpid())
	    pid_file = open(GitAutoDeploy.CONFIG_PID_FILE, 'w')
            pid_file.truncate()
            pid_file.write(str(os.getpid()))
            pid_file.close()
             
        server = HTTPServer(('', GitAutoDeploy.getConfig()['port']), GitAutoDeploy)
        server.serve_forever()
    except (KeyboardInterrupt, SystemExit) as e:
        if(e): # wtf, why is this creating a new line?
            print >> sys.stderr, e

        if(not server is None):
            server.socket.close()

        if(not GitAutoDeploy.quiet):
            print 'Goodbye'

if __name__ == '__main__':
     main()
