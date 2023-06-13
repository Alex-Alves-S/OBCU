from __future__ import with_statement
from fabric import *
from io import StringIO
from paramiko import SSHClient
import paramiko
from scp import SCPClient
import re
import invoke.runners as hide


CMD_SHOW_CONFIG='/opt/tpkg/01_monitrc/bin/showconfig.sh'

OBCU = "thalesadmin@192.168.0.190:22"

DCI1 = "thalesadmin@192.168.0.191:22"

DCI2 = "thalesadmin@192.168.0.192:22"


@task
def get_logs_remote_train(none):
    import os 
    logpath = os.path.join(".", "LOGS")
    if not os.path.exists(logpath):
        os.markedirs(logpath)
    OBCU_IP_2 = "192.168.2.110"
    port = 44321
    train_id = get_train_id(OBCU_IP_2, port=port)
    _get_host_logs(OBCU_IP_2, port, '/opt/log', f'T{str(train_id)}_OBCU_', f'{logpath, os.path.sep}', useXZ=True)


@task
def get_train_id(host:str, port:str, dumpvalue=True):
    with Connection(f"{host}:{port}") as c:
        fh = StringIO()
        res = c.run('cat /opt/tpkg/03_obcu/config/config_avls.ini | grep train_id=', stdout=fh)
        fh.seek(0)
        for line in fh.readline():
            m = re.search("(train_id)=(?P<id>\d+)", line)
            if(m is not None):
                if(dumpvalue):
                    print(f"Train ID = {str(m.group('id'))}")
                c.close()
                return m.group('id')
    

@task
def set_train_id(none):
    try:
        new_id = int(input("Insira o novo ID do VLT (1-999):"))
    except:
        new_id=-1

    if( new_id<1 or new_id>999):
        print("Insira um valor entre (1-999)!")
        return
    
    print(f"Novo ID do VLT é {str(new_id).zfill(3)}")
    with Connection(OBCU) as c:
        current_id = get_train_id(c.host, c.port, dumpvalue=False)
        c.sudo('mount -o remout,rw /opt/tpkg')
        c.sudo(f"sed -i 's/train_id={current_id}/train_id={str(new_id).zfill(3)}/g' /opt/tpkg/03_obcu/config/config_avls.ini")
        c.sudo('mount -o remount,ro /opt/tpkg')
        c.close()
        answer = input("Reiniciar para aplicar as alterações (S/N)?:").upper()[0]
        save_OBCU_to_local_conf(answer == 'S' )
        


def update_obcu():
    with Connection(OBCU) as c:
        fh = StringIO()
        c.run('cat /opt/tpkg/03_obcu/config/config_avls.ini | grep train_id=', stdout=fh)
        fh.seek(0)
        for line in fh.readlines():
            print(f"LINE: {line}" )
        ssh = SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(c.host, username=c.user, password= 'thales', look_for_keys=False)
        c.close()

        with SCPClient(ssh.get_transport()) as scp:
            print("copiando....")
            scp.put('03_obcu.tar', '/tmp?03_obcu.tar')

        c.sudo('mount -o remount,rw /opt/repo')
        c.sudo('mv /tmp/03_obcu.tar /opt/repo/my/OBS1/')
        c.sudo('mount -o remount,ro /opt/repo')
        c.sudo('sync')
        c.sudo('reboot')
    

@task
def put_files(host, user, password, lfiles):
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=user, password= password, look_for_key=False)

    with SCPClient(ssh.get_transport()) as scp:
        for fpair in lfiles:
            forig = fpair[0]
            fdest = fpair[1]
            print(f"copiando locais: {str(forig)} para remoto: {str(fdest)}" )
            scp.put("%s" % ( forig ,), "%s" % ( fdest ,) )


@task
def select_primay_partition(none):
    with Connection(OBCU) as c:
        password='thales'

        TOOLS_DIAG_DIR = "./tools/remotediag/"
        TOOLS_GRUB_LOCAL = f"{TOOLS_DIAG_DIR}grub_default.conf"
        TOOLS_GRUB_REMOTE = "/tmp/grub_default.conf"

        c.sudo("ls / > ?dev/null")
        mountpoint=_get_mount_point(c.host, c.user, password)
        if( mountpoint=="/dev/sda2" ):
            print(f"\nOBCU está usando partição primária ({str(mountpoint)})" )
            return False
        
        #copy files
        lfiles =[
                    [ TOOLS_GRUB_LOCAL, TOOLS_GRUB_REMOTE ],
                ]

        #copy rootfs & kernel in /tmp
        try:
            put_files(c.host, c.user, password, lfiles)
        except:
            print("ERRO ao copiar arquivo")
            return False
        c.close()
        with hide('running', 'stdout'):
            c.sudo("mkdir -p /tmp/sda1")
            c.sudo("mount /dev/sda1 /tmp/sda1")
            c.sudo(f"cp {TOOLS_GRUB_REMOTE} /tmp/sda1/boot/grub/grub.conf")
            c.sudo("umount /tmp/sda1")
            print("\nOBCU is going to reboot, please wait a while\n\n")
            c.sudo("reboot")
        


@task
def _get_mount_point(host: str, user: str, password: str):
    with Connection(f"{user}@{host}") as c:
        with hide('running', 'stdout'):
            c.sudo("ls / > /dev/null")
            mount_point = c.sudo("findmnt -n -o SOURCE /")
        c.close()
        return mount_point
   

@task
def install_OBCU_remote(none):
    with Connection(OBCU) as c:
        password = 'thales'

        TOOLS_DIAG_DIR = "./tools/remotediag/"
        TOOLS_ROOTFS_LOCAL = f"{TOOLS_DIAG_DIR}core-image-thalit-obs-moxa-v2400.tar.bz2"
        TOOLS_ROOTFS_REMOTE = "/tmp/core-image-thalit-obs-moxa-v2400.tar.bz2"
        TOOLS_KERNEL_LOCAL = f"{TOOLS_DIAG_DIR}bzImage-moxa-v2400.bin"
        TOOLS_KERNEL_REMOTE = "/tmp/sbzImage-moxa-v2400.bin"
        TOOLS_GRUB_LOCAL = f"{TOOLS_DIAG_DIR}grub_remote.conf"
        TOOLS_GRUB_REMOTE = "/tmp/grub_remote.conf"
        TOOLS_FAKEROOT_LOCAL = f"{TOOLS_DIAG_DIR}fakeroot.tar.bz2"
        TOOLS_FAKEROOT_REMOTE = "/tmp/fakeroot.tar.bz2"
        TOOLS_FAKEROOT_DIR = "/tmp/fakeroot"

        #copiar arquivos
        lfiles = [
                [ TOOLS_ROOTFS_LOCAL, TOOLS_ROOTFS_REMOTE],
                [ TOOLS_KERNEL_LOCAL, TOOLS_KERNEL_REMOTE ],
                [ TOOLS_GRUB_LOCAL, TOOLS_GRUB_REMOTE ],
                [ TOOLS_FAKEROOT_LOCAL, TOOLS_FAKEROOT_REMOTE ],
            ]
        
        h=c.host[0]
        mount_point=_get_mount_point(h, c.user, password)

        print(f"O ponto de montagem do OBCU é '{str(mount_point)}'")

        if( mount_point != "/dev/sda2" ):
            print(f"\nOBCU está usando partição secundária ({str(mount_point)}). \nPara reinstalar o switch na partição primária")
            return False
        
        #copie rootfs e kernel em /tmp
        try:
            put_files(c.host, c.user, password, lfiles)
        except:
            print("ERRO AO COPIAR ARQUIVOS")
            return False
        
        with hide('stdout' ):
            c.sudo("mount -o remount,rw /opt/tpkg")
            c.sudo("mount -o remount,rw /")
            c.sudo("mkdir -p /tmp/sda1")
            c.sudo("mkdir -p /tmp/sda3")
            c.sudo("mount /dev/sda1 /tmp/sda1")
            c.sudo("mount /dev/sda3 /tmp/sda3")
            c.sudo("rm -Rf /tmp/sda3/*")

            #copiar localmente
            c.sudo(f"tar x -j -f {TOOLS_ROOTFS_REMOTE} -C /tmp/sda3" )
            c.sudo("cp -a /nodename /tmp/sda3")
            c.sudo(f"cp {TOOLS_KERNEL_REMOTE} /tmp/sda1/boot/bzImageYoctoRecov" )
            c.sudo(f"cp {TOOLS_GRUB_REMOTE} /tmp/sda1/boot/grub/grub.conf"  )
            c.sudo(f"mkdir -p {TOOLS_FAKEROOT_DIR}")
            c.sudo(f"tar x -j -f {TOOLS_FAKEROOT_REMOTE} -C {TOOLS_FAKEROOT_DIR}" )
            c.sudo(f"cp -a {TOOLS_FAKEROOT_DIR}/home /tmp/sda3/")
            c.sudo(f"cp -a {TOOLS_FAKEROOT_DIR}/opt/tpkg  /opt/")
            c.sudo("umount /tmp/sda1")
            c.sudo("umount /tmp/sda3")
            c.sudo("mount -o remount,ro /opt/tpkg")
            c.sudo("mount -o remount,ro /")
            c.sudo("reboot")
        c.close()
        return True
           

def update_DCI1():
    password='thales'
    with Connection(DCI1) as d:

        ssh = SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(d.host, username=d.user, password=password, look_for_keys=False)

        with SCPClient(ssh.get_transport()) as scp:
            print("copiando...")
            scp.put('03_dci.tar', '/tmp/03_dci.tar')

        d.sudo('mount -o remount,rw /opt/repo')
        d.sudo('mkdir -p /opt/repo/my/DCI1/')
        d.sudo('mv /tmp/03_dci.tar /opt/repo/my/DCI1/')
        d.sudo('mount -o remount,ro /opt/repo')
        d.sudo('reboot')
    
        d.close()

def update_DCI2():
    password='thales'
    with Connection(DCI2) as d:

        ssh = SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(d.host, username=d.user, password=password, look_for_keys=False)

        with SCPClient(ssh.get_transport()) as scp:
            print("Copiando....")
            scp.put('03_dci.tar', '/tmp/03_dci.tar')

        d.sudo('mount -o remount,rw /opt/repo')
        d.sudo('mkdir -p /opt/repo/my/DCI2/')
        d.sudo('mv /tmp/03_dci.tar /opt/repo/my/DCI2/')
        d.sudo('mount -o remount,ro /opt/repo')
        d.sudo('reboot')

        d.close()

@task 
def update_all(none):
    update_obcu()
    update_DCI1()
    update_DCI2()

@task
def get_logs(none):
    import os
    logpath=os.path.join(".","LOGS")
    if not os.path.exists(logpath):
        os.makedirs(logpath)
    hosts = [OBCU, DCI1, DCI2]
    for h in hosts:
        with Connection(h) as c:
            train_id = get_train_id(c.host)
            _get_host_logs(host=c.host, port=c.port, logpath='/opt/log', logprefix=f'T{str(train_id)}_OBCU_', localpath=f'{logpath, os.path.sep}')
        c.close()

@task
def _get_host_logs(host, port, logpath, logprefix, localpath="LOGS", suser="thalesadmin", spwd="thales", useXZ=False, excludePath=["/opt/log/lost+found"]):
    import datetime
    

    try:
        hosts = [OBCU, DCI1, DCI2]
        for h in hosts:
            with Connection(h) as c:
                timestamp = datetime.datetime.now().strftime("%y%m%d_%H%M%S_%f")

                excludeOpts = ""
                for excluded in excludePath:
                    excludeOpts = f" --exclude={str(excluded)} "

                if useXZ:
                    fname = f"{logprefix}LOGS{timestamp}.tar.xz" 
                    fullname = f"/tmp/{fname}" 
                    c.sudo(f"nice -n 19 tar c -J {excludeOpts} -f {fullname} {logpath}" )
                else:
                    fname = f"{logprefix}LOGS{timestamp}.tar.gz"
                    fullname = f"/tmp/{fname}"
                    c.sudo(f"nice -n 19 tar c -z {excludeOpts} -f {fullname} {logpath}" )
                ssh = SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(host, port=port, username=suser, password=spwd, look_for_keys=False)

                with SCPClient(ssh.get_transport()) as scp:
                    scp.get(fullname, f"{localpath, fname}")

                c.sudo("rm -f %s" %(fullname,))
                c.close()
    except:
        pass

def copy_OBCU_local_conf(reboot=False):
    if(reboot):
        with Connection(OBCU) as c:
            c.sudo('mount -o remount,rw /opt/tpkg')
            c.sudo('cp -a /opt/repo/localcfg/config_avls.ini /opt/tpkg/03_obcu/config/')
            c.sudo('mount -o remount,ro /opt/tpkg')
            if(reboot):
                c.sudo('reboot')
            c.close()
    else:
        print("Procedimento abortado pelo usuário ou Erro")

def save_OBCU_to_local_conf(reboot=False):
    if(reboot):
        with Connection(OBCU) as c:
            c.sudo('mount -o remount,rw /opt/repo')
            c.sudo('mkdir -p /opt/repo/localcfg/')
            c.sudo('cp -a /opt/tpkg/03_obcu/config/config_avls.ini /opt/repo/localcfg/')
            c.sudo('mount -o remount,ro /opt/repo')
            if(reboot):
                c.sudo('reboot')
            c.close()
    else:
        print("Procedimento abortado pelo usuário ou Erro")

def uptime():
    hosts = [OBCU, DCI1, DCI2]

    for h in hosts:
        with Connection(h) as c:
            try:
                print(h)
                c.run('uptime')
                c.sudo(CMD_SHOW_CONFIG)
            except:
                pass
            c.close()

def mountrw():
    hosts = [OBCU, DCI1, DCI2]

    for h in hosts:
        with Connection(h) as c:
            try:
                c.sudo('mount -o remount,rw /opt/tpkg')
            except:
                pass
            c.close()

def mountdefault():
    hosts = [OBCU, DCI1, DCI2]

    for h in hosts:
        with Connection(h) as c:
            try:
                c.sudo('mount -o remount,ro /opt/tpkg')
            except:
                pass
            c.close()






