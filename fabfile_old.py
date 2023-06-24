from __future__ import with_statement
from fabric import *
from fabric.contrib.console import confirm
from StringIO import StringIO
from paramiko import SSHClient
import paramiko
from scp import SCPClient
import re

G_OBCU = {}
G_DCI1 = {}
G_DCI2 = {}

G_OBCU['ip'] = '192.168.0.190'
G_DCI1['ip'] = '192.168.0.191'
G_DCI2['ip'] = '192.168.0.192'

CMD_SHOW_CONFIG='/opt/tpkg/01_monitrc/bin/showconfig.sh'

def getLogsRemoteTrain():
    import os
    logpath=os.path.join(".", "LOGS")
    if not os.path.exists(logpath):
        os.makedirs(logpath)
    sOBCUHost="192.168.2.110"
    port=44321
    trainid=getTrainId(sOBCUHost, port=port)
    _getHostLogs(sOBCUHost, 44321, '/opt/log', 'T%s_OBCU_'%(str(trainid),), "%s%s"%(logpath, os.path.sep,), useXZ=True)

def getTrainId(host=G_OBCU["ip"], port=22, dumpvalue=True):
    
    env.user = 'thalesadmin'
    env.password = 'thales'
    env.hosts = [ host ]
    env.port = port
    env.warn_only = True

    for h in env.hosts:
        env.host_string = '%s@%s:%s' %(env.user, h, str(env.port), )
        fh = StringIO();
        res = run('cat /opt/tpkg/03_obcu/config/config_avls.ini | grep train_id=', stdout=fh)
        fh.seek(0)
        for line in fh.readlines():
            m = re.search("(train_id)=(?P<id>\d+)", line)
            if(m is not None):
                if(dumpvalue):
                    print("TRAIN ID = %s" % ( str(m.group("id"))  ))
                return m.group("id")

def setTrainId():
    try:
        newID = int(raw_input("Insert new TrainID (1-999):"))
    except:
        newID=-1

    if( newID<1 or newID>999):
        print("Please enter a value in (1-999)!")
        return

    print("New train ID will be %s" %(str(newID).zfill(8)))

    env.user = 'thalesadmin'
    env.password = 'thales'
    env.hosts = [ G_OBCU['ip'] ]
    env.warn_only = True

    for h in env.hosts:
        env.host_string = '%s@%s' %(env.user, h, )
        currentID = getTrainId(host=G_OBCU['ip'], port=22, dumpvalue=False)
        sudo('mount -o remount,rw /opt/tpkg')
        sudo("sed -i 's/train_id=%s/train_id=%s/g' /opt/tpkg/03_obcu/config/config_avls.ini" % ( currentID, str(newID).zfill(8) ))
        sudo('mount -o remount,ro /opt/tpkg')

    answer = raw_input("Reboot to apply the changes (Y/N)?:")
    saveOBCUToLocalConf( (str(answer).upper()[0] == 'Y' ) )

def updateOBCU():
    env.user = 'thalesadmin'
    env.password = 'thales'
    env.hosts = [ G_OBCU['ip'] ]
    env.warn_only = True

    for h in env.hosts:
        env.host_string = '%s@%s' %(env.user, h, )
        fh = StringIO();
        run('cat /opt/tpkg/03_obcu/config/config_avls.ini | grep train_id=', stdout=fh)
        fh.seek(0)
        for line in fh.readlines():
            print("LINE: %s" %(line) )
        ssh = SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(G_OBCU['ip'], username=env.user, password=env.password,look_for_keys=False)

        with SCPClient(ssh.get_transport()) as scp:
            print("copying....")
            scp.put('03_obcu.tar', '/tmp/03_obcu.tar')

        sudo('mount -o remount,rw /opt/repo')
        sudo('mv /tmp/03_obcu.tar /opt/repo/my/OBS1/')
        sudo('mount -o remount,ro /opt/repo')
        sudo('sync')
        sudo('reboot')

def putFiles(host, user, password, lfiles):
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=user, password=password,look_for_keys=False)

    with SCPClient(ssh.get_transport()) as scp:
        for fpair in lfiles:
            forig = fpair[0]
            fdest = fpair[1]
            print("copying local: %s to remote: %s" %(str(forig), str(fdest), ) )
            scp.put("%s" % ( forig ,), "%s" % ( fdest ,) )


def selectPrimaryPartition():
    env.user = 'thalesadmin'
    env.password = 'thales'
    env.hosts = [ G_OBCU['ip'] ]
    env.warn_only = True
    host=env.hosts[0]
    env.host_string = '%s@%s' %(env.user, host, )

    TOOLS_DIAG_DIR = "./tools/remotediag/"
    TOOLS_GRUB_LOCAL = "%sgrub_default.conf" % (TOOLS_DIAG_DIR,)
    TOOLS_GRUB_REMOTE = "/tmp/grub_default.conf"

    sudo("ls / > /dev/null")
    mountpoint=_getMountPoint(host, env.user, env.password )
    if( mountpoint=="/dev/sda2" ):
        print("\nOBCU is using primary partition (%s)" %(str(mountpoint), ) )
        return False

    #copy files
    lfiles = [
                [ TOOLS_GRUB_LOCAL, TOOLS_GRUB_REMOTE ],
            ]

    #copy rootfs & kernel in /tmp
    try:
        putFiles( G_OBCU['ip'], env.user, env.password, lfiles)
    except:
        print "ERROR COPYING FILES"
        return False

    with hide('running', 'stdout' ):
        sudo("mkdir -p /tmp/sda1")
        sudo("mount /dev/sda1 /tmp/sda1")
        sudo("cp %s /tmp/sda1/boot/grub/grub.conf"  % (TOOLS_GRUB_REMOTE,) )
        sudo("umount /tmp/sda1")
        print("\nOBCU is going to reboot, please wait a while\n\n")
        sudo("reboot")

def _getMountPoint(host,user="thalesadmin",password="thales"):
    """
    get current rootfs mountpoint
    """
    env.user = user
    env.password = password
    env.hosts = [ host ]
    env.warn_only = True
    host=env.hosts[0]
    env.host_string = '%s@%s' %(env.user, host, )
    #check current rootfs mountpoint
    with hide('running', 'stdout' ):
        #to discard the message shown for first sudo login
        #"We trust you have received the usual lecture from the local System.."
        sudo("ls / > /dev/null")
        mountpoint=sudo("findmnt -n -o SOURCE /")
    return mountpoint

def installOBCURemote():
    env.user = 'thalesadmin'
    env.password = 'thales'
    env.hosts = [ G_OBCU['ip'] ]
    env.warn_only = True

    TOOLS_DIAG_DIR = "./tools/remotediag/"
    TOOLS_ROOTFS_LOCAL = "%score-image-thalit-obs-moxa-v2400.tar.bz2" % (TOOLS_DIAG_DIR,)
    TOOLS_ROOTFS_REMOTE = "/tmp/core-image-thalit-obs-moxa-v2400.tar.bz2"
    TOOLS_KERNEL_LOCAL = "%sbzImage-moxa-v2400.bin" % (TOOLS_DIAG_DIR,)
    TOOLS_KERNEL_REMOTE = "/tmp/sbzImage-moxa-v2400.bin"
    TOOLS_GRUB_LOCAL = "%sgrub_remote.conf" % (TOOLS_DIAG_DIR,)
    TOOLS_GRUB_REMOTE = "/tmp/grub_remote.conf"
    TOOLS_FAKEROOT_LOCAL = "%sfakeroot.tar.bz2" % (TOOLS_DIAG_DIR,)
    TOOLS_FAKEROOT_REMOTE = "/tmp/fakeroot.tar.bz2"
    TOOLS_FAKEROOT_DIR = "/tmp/fakeroot"

    #copy files
    lfiles = [
                [ TOOLS_ROOTFS_LOCAL, TOOLS_ROOTFS_REMOTE],
                [ TOOLS_KERNEL_LOCAL, TOOLS_KERNEL_REMOTE ],
                [ TOOLS_GRUB_LOCAL, TOOLS_GRUB_REMOTE ],
                [ TOOLS_FAKEROOT_LOCAL, TOOLS_FAKEROOT_REMOTE ],
            ]

    h=env.hosts[0]
    env.host_string = '%s@%s' %(env.user, h, )
    mountpoint=_getMountPoint(h, env.user, env.password )

    print("OBCU's mount point is '%s'" %(str(mountpoint), ) )

    if( mountpoint != "/dev/sda2" ):
        print("\nOBCU is using secondary partition (%s).\nTo reinstall switch on primary partition" %(str(mountpoint), ) )
        return False

    #copy rootfs & kernel in /tmp
    try:
        putFiles( G_OBCU['ip'], env.user, env.password, lfiles)
    except:
        print "ERROR COPYING FILES"
        return False

    with hide('stdout' ):
        sudo("mount -o remount,rw /opt/tpkg")
        sudo("mount -o remount,rw /")
        sudo("mkdir -p /tmp/sda1")
        sudo("mkdir -p /tmp/sda3")
        sudo("mount /dev/sda1 /tmp/sda1")
        sudo("mount /dev/sda3 /tmp/sda3")
        sudo("rm -Rf /tmp/sda3/*")

        #copy locally
        sudo("tar x -j -f %s -C /tmp/sda3" % (TOOLS_ROOTFS_REMOTE,) )
        sudo("cp -a /nodename /tmp/sda3")
        sudo("cp %s /tmp/sda1/boot/bzImageYoctoRecov" % (TOOLS_KERNEL_REMOTE,) )
        sudo("cp %s /tmp/sda1/boot/grub/grub.conf"  % (TOOLS_GRUB_REMOTE,) )
        sudo("mkdir -p %s" %(TOOLS_FAKEROOT_DIR,))
        sudo("tar x -j -f %s -C %s" % (TOOLS_FAKEROOT_REMOTE, TOOLS_FAKEROOT_DIR,) )
        sudo("cp -a %s/home /tmp/sda3/" %(TOOLS_FAKEROOT_DIR,))
        sudo("cp -a %s/opt/tpkg  /opt/" %(TOOLS_FAKEROOT_DIR,))
        sudo("umount /tmp/sda1")
        sudo("umount /tmp/sda3")
        sudo("mount -o remount,ro /opt/tpkg")
        sudo("mount -o remount,ro /")
        sudo("reboot")

    return True


def updateDCI1():
    env.user = 'thalesadmin'
    env.password = 'thales'
    env.hosts = [ G_DCI1['ip'] ]
    env.warn_only = True

    for h in env.hosts:
        env.host_string = '%s@%s' %(env.user, h, )
        ssh = SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(G_DCI1['ip'], username=env.user, password=env.password,look_for_keys=False)

        with SCPClient(ssh.get_transport()) as scp:
            print("copying....")
            scp.put('03_dci.tar', '/tmp/03_dci.tar')

        sudo('mount -o remount,rw /opt/repo')
        sudo('mkdir -p /opt/repo/my/DCI1/')
        sudo('mv /tmp/03_dci.tar /opt/repo/my/DCI1/')
        sudo('mount -o remount,ro /opt/repo')
        sudo('reboot')

def updateDCI2():
    env.user = 'thalesadmin'
    env.password = 'thales'
    env.hosts = [ G_DCI2['ip'] ]
    env.warn_only = True

    for h in env.hosts:
        env.host_string = '%s@%s' %(env.user, h, )
        ssh = SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(G_DCI2['ip'], username=env.user, password=env.password,look_for_keys=False)

        with SCPClient(ssh.get_transport()) as scp:
            print("copying....")
            scp.put('03_dci.tar', '/tmp/03_dci.tar')

        sudo('mount -o remount,rw /opt/repo')
        sudo('mkdir -p /opt/repo/my/DCI2/')
        sudo('mv /tmp/03_dci.tar /opt/repo/my/DCI2/')
        sudo('mount -o remount,ro /opt/repo')
        sudo('reboot')

def updateAll():
    updateOBCU()
    updateDCI1()
    updateDCI2()

def getLogs():
    import os
    logpath=os.path.join(".", "LOGS")
    if not os.path.exists(logpath):
        os.makedirs(logpath)
    trainid=getTrainId(G_OBCU['ip'])
    _getHostLogs(host=G_OBCU['ip'], port=22, logpath='/opt/log', logprefix='T%s_OBCU_'%(str(trainid),), localpath="%s%s"%(logpath, os.path.sep,))
    _getHostLogs(host=G_DCI1['ip'], port=22, logpath='/opt/log', logprefix='T%s_DCI1_'%(str(trainid), ), localpath="%s%s"%(logpath, os.path.sep,))
    _getHostLogs(host=G_DCI2['ip'], port=22, logpath='/opt/log', logprefix='T%s_DCI2_'%(str(trainid),), localpath="%s%s"%(logpath, os.path.sep,))

def _getHostLogs(host, port, logpath, logprefix, localpath="LOGS", suser="thalesadmin", spwd="thales", useXZ=False, excludePath=["/opt/log/lost+found"]):
    import datetime

    try:
        env.user = suser
        env.password = spwd
        env.hosts = [ host ]
        env.port = port
        env.warn_only = True

        for h in env.hosts:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            env.host_string = '%s@%s:%s' %(env.user, h, port,)

            excludeOpts = ""
            for excluded in excludePath:
                excludeOpts = " --exclude=%s " % (str(excluded) ,)

            if useXZ:
                fname = "%sLOGS%s.tar.xz" % (logprefix, timestamp, )
                fullname = "/tmp/%s" % (fname, )
                sudo("nice -n 19 tar c -J %s -f %s %s" %(excludeOpts, fullname,logpath) )
            else:
                fname = "%sLOGS%s.tar.gz" % (logprefix, timestamp, )
                fullname = "/tmp/%s" % (fname, )
                sudo("nice -n 19 tar c -z %s -f %s %s" %(excludeOpts, fullname,logpath) )
            ssh = SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(host, port=port, username=env.user, password=env.password,look_for_keys=False)

            with SCPClient(ssh.get_transport()) as scp:
                scp.get(fullname, "%s%s"%(localpath,fname,) )

            sudo("rm -f %s" %(fullname,))
    except:
        pass


def copyOBCULocalConf(reboot=False):
    env.user = 'thalesadmin'
    env.password = 'thales'
    env.hosts = [ G_OBCU['ip'] ]
    env.warn_only = True

    for h in env.hosts:
        env.host_string = '%s@%s' %(env.user, h, )
        sudo('mount -o remount,rw /opt/tpkg')
        sudo('cp -a /opt/repo/localcfg/config_avls.ini /opt/tpkg/03_obcu/config/')
        sudo('mount -o remount,ro /opt/tpkg')
        if(reboot):
            sudo('reboot')

def saveOBCUToLocalConf(reboot=False):
    env.user = 'thalesadmin'
    env.password = 'thales'
    env.hosts = [ G_OBCU['ip'] ]
    env.warn_only = True

    for h in env.hosts:
        env.host_string = '%s@%s' %(env.user, h, )
        sudo('mount -o remount,rw /opt/repo')
        sudo('mkdir -p /opt/repo/localcfg/')
        sudo('cp -a /opt/tpkg/03_obcu/config/config_avls.ini /opt/repo/localcfg/')
        sudo('mount -o remount,ro /opt/repo')
        if(reboot):
            sudo('reboot')

def uptime():
    global G_OBCU, G_DCI1, G_DCI2
    env.hosts = [ G_OBCU['ip'], G_DCI1['ip'], G_DCI2['ip'] ]
    env.user = 'thalesadmin'
    env.password = 'thales'
    for h in env.hosts:
        try:
            print h
            env.host = h
            env.host_string = '%s@%s' %(env.user, h, )
            run('uptime')
            sudo(CMD_SHOW_CONFIG)
        except:
            pass

def mountrw():
    global G_OBCU, G_DCI1, G_DCI2
    env.hosts = [ G_OBCU['ip'], G_DCI1['ip'], G_DCI2['ip'] ]
    env.user = 'thalesadmin'
    env.password = 'thales'
    for h in env.hosts:
        try:
            env.host_string = '%s@%s' %(env.user, h, )
            sudo('mount -o remount,rw /opt/tpkg')
        except:
            pass

def mountdefault():
    global G_OBCU, G_DCI1, G_DCI2
    env.hosts = [ G_OBCU['ip'], G_DCI1['ip'], G_DCI2['ip'] ]
    env.user = 'thalesadmin'
    env.password = 'thales'
    for h in env.hosts:
        try:
            env.host_string = '%s@%s' %(env.user, h, )
            sudo('mount -o remount,ro /opt/tpkg')
        except:
            pass
