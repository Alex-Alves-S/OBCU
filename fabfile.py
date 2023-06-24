from __future__ import with_statement
from fabric import *
from paramiko import SSHClient
import paramiko
from scp import SCPClient
import re
import invoke.runners as hide
from invoke import Responder

# Informações de Conexão

CMD_SHOW_CONFIG='/opt/tpkg/01_monitrc/bin/showconfig.sh'
OBCU = Connection("thalesadmin@192.168.0.190:22", connect_kwargs={'password': 'thales'}, connect_timeout=10)
DCI1 = Connection("thalesadmin@192.168.0.191:22", connect_kwargs={'password': 'thales'})
DCI2 = Connection("thalesadmin@192.168.0.192:22", connect_kwargs={'password': 'thales'})


# Comandos principais - parametro ctx: argumento de contexto para chamada fab

@task 
def update_all(ctx):
    update_obcu()
    update_DCI1()
    update_DCI2()


@task
def set_train_id(ctx):
    new_id = 0
    while True:
        try:
            new_id = int(input("Insira o prefixo do VLT (1-999):"))
        except:
            print("ERRO: insira um valor entre 1 e 999!")
        if new_id > 0 and new_id < 1000:
            break
    print(f"Prefixo do VLT: {str(new_id).zfill(8)}")
    print("Configurando, aguarde...")   
    OBCU.open()
    OBCU.connect_kwargs["password"]
    sudopass = Responder(pattern=r'\[sudo\] password:',response='thales\n')
    current_id = _get_train_id(dumpvalue = False)
    OBCU.sudo('mount -o remount,rw /opt/tpkg', pty = True ,watchers=[sudopass])
    OBCU.sudo(f"sed -i 's/train_id={current_id}/train_id={str(new_id).zfill(8)}/g' /opt/tpkg/03_obcu/config/config_avls.ini", pty = True,watchers=[sudopass])
    OBCU.sudo('mount -o remount,ro /opt/tpkg', pty = True ,watchers=[sudopass])
    OBCU.close()
    answer = input("Reiniciar para aplicar as alterações [S/N]?:").upper()[0]
    save_OBCU_to_local_conf(answer == 'S' )


@task
def get_train_id( dumpvalue=True):
    OBCU = Connection("thalesadmin@192.168.0.190:22", connect_kwargs={'password':'thales'})
    OBCU.connect_kwargs["password"]
    OBCU.open()
    res = str(OBCU.run('cat /opt/tpkg/03_obcu/config/config_avls.ini | grep train_id='))
    OBCU.close()
    teste = res.split(' ')
    prefixo = re.search("(train_id)=(?P<id>\d+)", teste[-2])
    if dumpvalue:
        print(f"Prefixo atual do VLT: {prefixo.group('id')}")
    return prefixo.group('id')


@task
def get_logs(ctx):
    import os
    logpath=os.path.join(".","LOGS")
    if not os.path.exists(logpath):
        os.makedirs(logpath)
    hosts = [OBCU, DCI1, DCI2]
    for conn in hosts:
        conn.open()
        
        train_id = get_train_id(conn.host)
        _get_host_logs(
            host=conn.host, 
            port=conn.port, 
            logpath='/opt/log', 
            logprefix=f'T{str(train_id)}_OBCU_', 
            localpath=f'{logpath, os.path.sep}'
            )
        conn.close()


@task
def get_logs_remote_train(ctx):
    import os 
    logpath = os.path.join(".", "LOGS")
    if not os.path.exists(logpath):
        os.markedirs(logpath)
    OBCU_IP_2 = "192.168.2.110"
    port = 44321
    train_id = get_train_id(OBCU_IP_2, port=port)
    _get_host_logs(OBCU_IP_2, port, '/opt/log', f'T{str(train_id)}_OBCU_', f'{logpath, os.path.sep}', useXZ=True)


# Comandos secundarios - são chamados pelos comandos principais

def update_DCI1():
    DCI1.open()
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(DCI1.host, username=DCI1.user, password=DCI1.connect_kwargs['password'], look_for_keys=False)
    with SCPClient(ssh.get_transport()) as scp:
        print("copiando...")
        scp.put('03_dci.tar', '/tmp/03_dci.tar')
        sudopass = Responder(pattern=r'\[sudo\] password:',response='thales\n')
    DCI1.sudo('mount -o remount,rw /opt/repo', pty = True,watchers=[sudopass])
    DCI1.sudo('mkdir -p /opt/repo/my/DCI1/', pty = True,watchers=[sudopass])
    DCI1.sudo('mv /tmp/03_dci.tar /opt/repo/my/DCI1/', pty = True,watchers=[sudopass])
    DCI1.sudo('mount -o remount,ro /opt/repo', pty = True,watchers=[sudopass])
    DCI1.sudo('reboot', pty = True,watchers=[sudopass])
    DCI1.close()


def update_DCI2():
    DCI2.open()
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(DCI2.host, username=DCI2.user, password=DCI2.connect_kwargs['password'], look_for_keys=False)
    with SCPClient(ssh.get_transport()) as scp:
        print("copiando...")
        scp.put('03_dci.tar', '/tmp/03_dci.tar')
        sudopass = Responder(pattern=r'\[sudo\] password:',response='thales\n')
    DCI2.sudo('mount -o remount,rw /opt/repo', pty = True,watchers=[sudopass])
    DCI2.sudo('mkdir -p /opt/repo/my/DCI1/', pty = True,watchers=[sudopass])
    DCI2.sudo('mv /tmp/03_dci.tar /opt/repo/my/DCI1/', pty = True,watchers=[sudopass])
    DCI2.sudo('mount -o remount,ro /opt/repo', pty = True,watchers=[sudopass])
    DCI2.sudo('reboot', pty = True,watchers=[sudopass])
    DCI2.close()


def update_obcu():
    print("Conectando...")
    try:
        OBCU.open()
    except TimeoutError as error:
        print("Ocorreu um erro ao conectar, tente novamente!")
        print(error)
    OBCU.run('cat /opt/tpkg/03_obcu/config/config_avls.ini | grep train_id=')
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(OBCU.host, username=OBCU.user, password=OBCU.connect_kwargs['password'], look_for_keys=False)
    with SCPClient(ssh.get_transport()) as scp:
        print("copiando....")
        scp.put('03_obcu.tar', '/tmp/03_obcu.tar')
        sudopass = Responder(pattern=r'\[sudo\] password:',response='thales\n')
    OBCU.sudo('mount -o remount,rw /opt/repo', pty = True,watchers=[sudopass])
    OBCU.sudo('mv /tmp/03_obcu.tar /opt/repo/my/OBS1/', pty = True,watchers=[sudopass])
    OBCU.sudo('mount -o remount,ro /opt/repo', pty = True,watchers=[sudopass])
    OBCU.sudo('sync', pty = True,watchers=[sudopass])
    OBCU.sudo('reboot', pty = True,watchers=[sudopass])
    OBCU.close()


def _get_train_id( dumpvalue=True):
    OBCU = Connection("thalesadmin@192.168.0.190:22", connect_kwargs={'password':'thales'})
    OBCU.connect_kwargs["password"]
    OBCU.open()
    res = str(OBCU.run('cat /opt/tpkg/03_obcu/config/config_avls.ini | grep train_id='))
    OBCU.close()
    teste = res.split(' ')
    prefixo = re.search("(train_id)=(?P<id>\d+)", teste[-2])
    if dumpvalue:
        print(f"Prefixo atual do VLT: {prefixo.group('id')}")
    return prefixo.group('id')


def copy_OBCU_local_conf(reboot=False):
    sudopass = Responder(pattern=r'\[sudo\] password:',response='thales\n')
    if(reboot):
        OBCU.open()
        OBCU.sudo('mount -o remount,rw /opt/tpkg', pty = True, watchers = [sudopass])
        OBCU.sudo('cp -a /opt/repo/localcfg/config_avls.ini /opt/tpkg/03_obcu/config/', pty = True, watchers = [sudopass])
        OBCU.sudo('mount -o remount,ro /opt/tpkg', pty = True, watchers = [sudopass])
        OBCU.close()
        if(reboot):
            OBCU.sudo('reboot', pty = True, watchers = [sudopass])
    else:
        print("Procedimento abortado pelo usuário ou Erro")


def save_OBCU_to_local_conf(reboot=False):
    sudopass = Responder(pattern=r'\[sudo\] password:',response='thales\n',)
    if(reboot):
        OBCU.open()
        OBCU.sudo('mount -o remount,rw /opt/repo', pty = True, watchers = [sudopass])
        OBCU.sudo('mkdir -p /opt/repo/localcfg/', pty = True, watchers = [sudopass])
        OBCU.sudo('cp -a /opt/tpkg/03_obcu/config/config_avls.ini /opt/repo/localcfg/', pty = True, watchers = [sudopass])
        OBCU.sudo('mount -o remount,ro /opt/repo', pty = True, watchers = [sudopass])
        if(reboot):
            OBCU.sudo('reboot', pty = True, watchers = [sudopass])
            OBCU.close()
            print("Procedimento realizado com sucesso!")
    else:
        print("Procedimento abortado pelo usuário ou Erro")


def uptime(ctx):
    hosts = [OBCU, DCI1, DCI2]
    sudopass = Responder(pattern=r'\[sudo\] password:',response='thales\n',)
    for h in hosts:
        h.open()
        try:
            print(h)
            h.run('uptime')
            h.sudo(CMD_SHOW_CONFIG, pty = True, watchers = [sudopass] )
        except:
            pass
        h.close()


def _get_host_logs(host, port, logpath, logprefix, localpath="LOGS", suser="thalesadmin", spwd="thales", useXZ=False, excludePath=["/opt/log/lost+found"]):
    import datetime
    sudopass = Responder(pattern=r'\[sudo\] password:',response='thales\n')

    try:
        hosts = [OBCU, DCI1, DCI2]
        for h in hosts:
                h.open()
                timestamp = datetime.datetime.now().strftime("%y%m%d_%H%M%S_%f")

                excludeOpts = ""
                for excluded in excludePath:
                    excludeOpts = f" --exclude={str(excluded)} "

                if useXZ:
                    fname = f"{logprefix}LOGS{timestamp}.tar.xz" 
                    fullname = f"/tmp/{fname}" 
                    h.sudo(f"nice -n 19 tar c -J {excludeOpts} -f {fullname} {logpath}",pty = True, watchers = [sudopass] )
                else:
                    fname = f"{logprefix}LOGS{timestamp}.tar.gz"
                    fullname = f"/tmp/{fname}"
                    h.sudo(f"nice -n 19 tar c -z {excludeOpts} -f {fullname} {logpath}", pty = True, watchers = [sudopass] )
                ssh = SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(host, port=port, username=suser, password=spwd, look_for_keys=False)

                with SCPClient(ssh.get_transport()) as scp:
                    scp.get(fullname, f"{localpath, fname}")

                h.sudo(f"rm -f {fullname}",pty = True, watchers = [sudopass])
                h.close()
    except:
        pass


# Install remoto OBCU - (não testado)


@task
def install_OBCU_remote(ctx):
    sudopass = Responder(pattern=r'\[sudo\] password:',response='thales\n')
    OBCU.open()
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
    mount_point=_get_mount_point(OBCU.host, OBCU.user, OBCU.connect_kwargs['password'])
    print(f"O ponto de montagem do OBCU é '{str(mount_point)}'")
    if mount_point != "/dev/sda2":
        print(f"\nOBCU está usando partição secundária ({str(mount_point)}). \nPara reinstalar troque para partição primária.")
        OBCU.close()
        return False
    #copie rootfs e kernel em /tmp
    try:
        put_files(OBCU.host, OBCU.user, OBCU.connect_kwargs['password'], lfiles)
    except:
        print("ERRO AO COPIAR ARQUIVOS!")
        OBCU.close()
        return False
    with hide('stdout' ):
        OBCU.sudo("mount -o remount,rw /opt/tpkg", pty = True, watchers = [sudopass])
        OBCU.sudo("mount -o remount,rw /", pty = True, watchers = [sudopass])
        OBCU.sudo("mkdir -p /tmp/sda1", pty = True, watchers = [sudopass])
        OBCU.sudo("mkdir -p /tmp/sda3", pty = True, watchers = [sudopass])
        OBCU.sudo("mount /dev/sda1 /tmp/sda1", pty = True, watchers = [sudopass])
        OBCU.sudo("mount /dev/sda3 /tmp/sda3", pty = True, watchers = [sudopass])
        OBCU.sudo("rm -Rf /tmp/sda3/*", pty = True, watchers = [sudopass])
        #copiar localmente
        OBCU.sudo(f"tar x -j -f {TOOLS_ROOTFS_REMOTE} -C /tmp/sda3" , pty = True, watchers = [sudopass])
        OBCU.sudo("cp -a /nodename /tmp/sda3", pty = True, watchers = [sudopass])
        OBCU.sudo(f"cp {TOOLS_KERNEL_REMOTE} /tmp/sda1/boot/bzImageYoctoRecov" , pty = True, watchers = [sudopass])
        OBCU.sudo(f"cp {TOOLS_GRUB_REMOTE} /tmp/sda1/boot/grub/grub.conf" , pty = True, watchers = [sudopass] )
        OBCU.sudo(f"mkdir -p {TOOLS_FAKEROOT_DIR}", pty = True, watchers = [sudopass])
        OBCU.sudo(f"tar x -j -f {TOOLS_FAKEROOT_REMOTE} -C {TOOLS_FAKEROOT_DIR}", pty = True, watchers = [sudopass] )
        OBCU.sudo(f"cp -a {TOOLS_FAKEROOT_DIR}/home /tmp/sda3/", pty = True, watchers = [sudopass])
        OBCU.sudo(f"cp -a {TOOLS_FAKEROOT_DIR}/opt/tpkg  /opt/", pty = True, watchers = [sudopass])
        OBCU.sudo("umount /tmp/sda1", pty = True, watchers = [sudopass])
        OBCU.sudo("umount /tmp/sda3", pty = True, watchers = [sudopass])
        OBCU.sudo("mount -o remount,ro /opt/tpkg", pty = True, watchers = [sudopass])
        OBCU.sudo("mount -o remount,ro /", pty = True, watchers = [sudopass])
        OBCU.sudo("reboot", pty = True, watchers = [sudopass])
        OBCU.close()
        return True


# Funções Gerais
def _get_mount_point():
    sudopass = Responder(pattern=r'\[sudo\] password:',response='thales\n')
    OBCU.open()
    OBCU.connect_kwargs['password']
    with hide('running', 'stdout'):
        OBCU.sudo("ls / > /dev/null", pty = True, watchers = [sudopass])
        mount_point = OBCU.sudo("findmnt -n -o SOURCE /", pty = True, watchers = [sudopass])
        OBCU.close()
        return mount_point
    

def put_files(ctx, host=None, user=None, password=None, lfiles=None):
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=user, password= password, look_for_key=False)
    with SCPClient(ssh.get_transport()) as scp:
        for fpair in lfiles:
            forig = fpair[0]
            fdest = fpair[1]
            print(f"copiando locais: {str(forig)} para remoto: {str(fdest)}" )
            scp.put(f"{ forig },{ fdest }")


def select_primay_partition(ctx):
    sudopass = Responder(pattern=r'\[sudo\] password:',response='thales\n')
    OBCU.open()
    TOOLS_DIAG_DIR = "./tools/remotediag/"
    TOOLS_GRUB_LOCAL = f"{TOOLS_DIAG_DIR}grub_default.conf"
    TOOLS_GRUB_REMOTE = "/tmp/grub_default.conf"
    OBCU.sudo("ls / > ?dev/null", pty = True, watchers = [sudopass])
    mountpoint=_get_mount_point(OBCU.host, OBCU.user, OBCU.connect_kwargs['password'])
    if mountpoint == "/dev/sda2":
        print(f"\nOBCU está usando partição primária ({str(mountpoint)})" )
        return False  
    #copy files
    lfiles =[[ TOOLS_GRUB_LOCAL, TOOLS_GRUB_REMOTE ],]
    #copy rootfs & kernel in /tmp
    try:
        put_files(OBCU.host, OBCU.user, OBCU.connect_kwargs['password'], lfiles)
    except:
        print("ERRO ao copiar arquivo!")
        return False
    with hide('running', 'stdout'):
        OBCU.sudo("mkdir -p /tmp/sda1", pty = True, watchers = [sudopass])
        OBCU.sudo("mount /dev/sda1 /tmp/sda1", pty = True, watchers = [sudopass])
        OBCU.sudo(f"cp {TOOLS_GRUB_REMOTE} /tmp/sda1/boot/grub/grub.conf", pty = True, watchers = [sudopass])
        OBCU.sudo("umount /tmp/sda1", pty = True, watchers = [sudopass])
        print("\nOBCU reiniciando, aguarde...\n\n")
        OBCU.sudo("reboot", pty = True, watchers = [sudopass])
        OBCU.close()
