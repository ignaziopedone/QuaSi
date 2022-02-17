
#ipython is automatically installed along with jupyter itself
#ipython -c "from notebook.auth import passwd; passwd()"
#python -c "from notebook.auth import passwd; print(passwd())"
#commands to use to create our password for the notebook and obtain its hashed version
#the result will be a unicode string thus the u in front of it below

import os


c = get_config()  # get the default jupyter configuration
# Kernel config
c.IPKernelApp.pylab = 'inline'  # if you want plotting support always in your notebook
# Notebook config
c.NotebookApp.notebook_dir = 'qkdsim'
#c.NotebookApp.allow_origin = u'qkdsim-2.0.com' # put your public IP Address here the ingress or kubernetes service public ip address
c.NotebookApp.ip = '*'
c.NotebookApp.allow_remote_access = True
c.NotebookApp.open_browser = True
# ipython -c "from notebook.auth import passwd; passwd()"
#c.NotebookApp.token='18dd29a53126ec5d02b50a1b04b6fd59ab64c6900b4ddfff'
c.NotebookApp.password = u'argon2:$argon2id$v=19$m=10240,t=10,p=8$D6umdQsXivZY3otFMv2Ygw$Nu5+a1slCVwGvEpzXwJLvQ' # we need an hashed password
#environment variable to select the port its gonna be running on
c.NotebookApp.port = int(os.environ.get("PORT", 8987))
c.NotebookApp.allow_root = True
#c.NotebookApp.allow_password_change = True
c.ConfigurableHTTPProxy.command = ['configurable-http-proxy', '--redirect-port', '80']
