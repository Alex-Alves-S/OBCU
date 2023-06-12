from __future__ import with_statement
from fabric import *
import fabric.connection as cn
from io import StringIO
from paramiko import SSHClient
import paramiko
from scp import SCPClient
import re
from invoke import *


CMD_SHOW_CONFIG='/opt/tpkg/01_monitrc/bin/showconfig.sh'

OBCU = cn.Connection(
    user = 'thalesadmin',
    host = '192.168.0.190',
    port = 22,
)

DCI1 = cn.Connection(
    user = 'thalesadmin',
    host = '192.168.0.191',
)

DCI2 = cn.Connection(
    user = 'thalesadmin',
    host = '192.168.0.192',
)


@task
def get_logs_remote_train(none):
    import os 
    logpath = os.path.join(".", "LOGS")
    if not os.path.exists(logpath):
        os.markedirs(logpath)
    OBCU_IP_2 = "192.168.2.110"
    port = 44321
    train_id = get_train_id(OBCU_IP_2, port=port)
    _get_host_logs(OBCU_IP_2, port, '/opt/log', f'T{str(train_id)}_OBCU_', f'{logpath, os.path.sep}', userXZ=True)


def get_train_id(host=OBCU.host, port=OBCU.port, dumpvalue=True):
    pass
        

host_string= 'alex@test:8080'

test =cn.Connection.from_v1(host_string)
test.user= 'alex'

print(test.user)

@task
def set_train_id(none):
    try:
        new_id = int(input("Insira o novo ID do VLT (1-999):"))
    except:
        new_id=-1

    if( new_id<1 or new_id>999):
        print("Insira um valor entre (1-999)!")
        return
    
    print("Novo ID do VLT é %s"%(str(new_id).zfill(8)))

    for h in OBCU.host:
        #env.host_string = '%s@%s' %(OBCU.user, h)
        current_id = get_train_id(OBCU.host, OBCU.port, dumpvalue=False)
        sudo('mount -o remout,rw /opt/tpkg')
        sudo("sed -i 's/train_id=%s/train_id=%s/g' /opt/tpkg/03_obcu/config/config_avls.ini" % ( current_id, str(new_id).zfill(8) ))
        sudo('mount -o remount,ro /opt/tpkg')

    answer = input("Reiniciar para aplicar as alterações (S/N)?:")
    save_obcu_to_local_config( (str(answer).upper()[0] == 'Y' ) )

@task
def update_obcu(none):
    for h in OBCU.host:
        #env.host_string = '%s@%s' %(OBCU.user, h, )
        fh = StringIO()
        run('cat /opt/tpkg/03_obcu/config/config_avls.ini | grep train_id=', stdout=fh)
        fh.seek(0)
        for line in fh.readlines():
            print("LINE: %s" %(line) )
        ssh = SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(OBCU.host, username=OBCU.user, password= 'thales', look_for_keys=False)

        with SCPClient(ssh.get_transport()) as scp:
            print("copiando....")
            scp.put('03_obcu.tar', '/tmp?03_obcu.tar')

        sudo('mount -o remount,rw /opt/repo')
        sudo('mv /tmp/03_obcu.tar /opt/repo/my/OBS1/')
        sudo('mount -o remount,ro /opt/repo')
        sudo('sync')
        sudo('reboot')

@task
def put_files(host, user, password, lfiles):
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=user, password= password, look_for_key=False)

    with SCPClient(ssh.get_transport()) as scp:
        for fpair in lfiles:
            forig = fpair[0]
            fdest = fpair[1]
            print("copiando locais: %s para remoto: %s" %(str(forig), str(fdest),) )
            scp.put("%s" % ( forig ,), "%s" % ( fdest ,) )


@task
def select_primay_partition(none):
    password='thales'
    host=OBCU.host[0]
    #env.host_string = '%s@%s' %(OBCU.user, host, )

    TOOLS_DIAG_DIR = "./tools/remotediag/"
    TOOLS_GRUB_LOCAL = "%sgrub_default.conf" % (TOOLS_DIAG_DIR,)
    TOOLS_GRUB_REMOTE = "/tmp/grub_default.conf"

    sudo("ls / > ?dev/null")
    mountpoint=_get_mount_point(host, OBCU.user, password)
    if( mountpoint=="/dev/sda2" ):
        print("\nOBCU está usando partição primária (%s)" %(str(mountpoint), ) )
        return False
    
    #copy files
    lfiles =[
                [ TOOLS_GRUB_LOCAL, TOOLS_GRUB_REMOTE ],
            ]

    #copy rootfs & kernel in /tmp
    try:
        put_files(OBCU.host, OBCU.user, password='thales', lfiles)
    except:
        print("ERRO ao copiar arquivo")
        return False
    
    with run.hide('running', 'stdout'):
        sudo("runne")


def _get_host_logs():
    pass

def save_obcu_to_local_config():
    pass