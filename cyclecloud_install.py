#!/usr/bin/python
# Prepare an Azure provider account for CycleCloud usage.
import argparse
import tarfile
from random import SystemRandom
from string import ascii_letters, digits
from subprocess import call
from os import path, makedirs, chdir, fdopen, remove
from urllib import urlretrieve
from shutil import rmtree, copyfile, move
from tempfile import mkstemp, mkdtemp

print "Creating temp directory " + tmpdir + " for installing CycleCloud"
tmpdir = mkdtemp()
cycle_root = "/opt/cycle_server"

def cleanUp():
    rmtree(tmpdir)    


def startCC():
    cs_cmd = cycle_root + "/cycle_server"
    call([cs_cmd, "start"])
    call([cs_cmd, "await_startup"])
    call([cs_cmd, "status"])

def _sslCert(randomPW):
    call(["/bin/keytool", "-genkey", "-alias", "CycleServer", "-keypass", randomPW, "-keystore", cycle_root + "/.keystore", "-storepass", randomPW, "-keyalg", "RSA", "-noprompt", "-dname", "CN=cycleserver.azure.com,OU=Unknown, O=Unknown, L=Unknown, ST=Unknown, C=Unknown"])
    call(["chown", "cycle_server.", cycle_root+"/.keystore"])
    call(["chmod", "600", cycle_root+"/.keystore" ])


def modifyCSConfig():
    # modify the CS config files
    cs_config_file = cycle_root + "/config/cycle_server.properties"

    randomPW = ''.join(SystemRandom().choice(ascii_letters + digits) for _ in range(16))
    # generate a self-signed cert
    _sslCert(randomPW)

    fh, abs_path = mkstemp()
    with fdopen(fh,'w') as new_config:
        with open(cs_config_file) as cs_config:
            for line in cs_config:
                if 'webServerMaxHeapSize' in line:
                    new_config.write('webServerMaxHeapSize=4096M')
                elif 'webServerPort' in line:
                    new_config.write('webServerPort=80')
                elif 'webServerSslPort' in line:
                    new_config.write('webServerSslPort=443')
                elif 'webServerEnableHttps' in line:
                    new_config.write('webServerEnableHttps=true')
                elif 'webServerKeystorePass' in line:
                    new_config.write('webServerKeystorePass=' + randomPW)
                else:
                    new_config.write(line)

    remove(cs_config)
    move(new_config, cs_config)


def generateSSHkey():
    # create an SSH private key for VM access
    homedir = path.expanduser("~")
    sshdir = homedir + "/.ssh"
    if not path.isdir(sshdir):
        makedirs(sshdir, mode="0700") 
    
    sshkeyfile = sshdir + "/cyclecloud.pem"
    if not path.isfile(sshkeyfile):
        call(["ssh-keygen", "-f", sshkeyfile, "-t", "rsa", "-b", "2048" "-P", '""'])

    # make the cyclecloud.pem available to the cycle_server process
    cs_sshdir = cycle_root + "/.ssh"
    cs_sshkeyfile = cs_sshdir + "/cyclecloud.pem"

    if not path.isdir(cs_sshdir):
        makedirs(cs_sshdir, mode="0700")
    
    if not path.isdir(cs_sshkeyfile):
        copyfile(sshkeyfile, cs_sshkeyfile)
        call(["chown", "-R", "cycle_server.", cs_sshdir])


def ccLicense():
    # get a license
    license_file = cycle_root + '/license.dat'
    urlretrieve(argparse.licenseURL, license_file)
    call(["chown", "cycle_server.", license_file])


def downloadAndInstallCC(args):    
    chdir(tmpdir)
    cc_url = args.downloadURL + "/cycle_server-all-linux64.tar.gz"
    cli_url = args.downloadURL + "/cyclecloud-cli.linux64.tar.gz"
    pogo_url = args.downloadURL + "/pogo-cli.linux64.tar.gz"

    print "Downloading CycleCloud from " + cc_url
    urlretrieve (cc_url, "cycle_server-all-linux64.tar.gz")
    print "Downloading CycleCloud CLI from " + cli_url
    urlretrieve (cli_url, "cyclecloud-cli.linux64.tar.gz")
    print "Downloading Pogo CLI from " + pogo_url
    urlretrieve (pogo_url, "pogo-cli.linux64.tar.gz")

    print "Unpacking tar files"
    cc_tar = tarfile.open("cycle_server-all-linux64.tar.gz", "r:gz")
    cc_tar.extractall(path=tmpdir)
    cc_tar.close()
    
    cli_tar = tarfile.open("cyclecloud-cli.linux64.tar.gz", "r:gz")
    cli_tar.extractall(path=tmpdir)
    cli_tar.close()

    pogo_tar = tarfile.open("pogo-cli.linux64.tar.gz", "r:gz")
    pogo_tar.extractall(path=tmpdir)
    pogo_tar.close()

    call(["cycle_server/install.sh", "--nostart"])


def installPreReq():
    call(["yum", "install", "-y", "java-1.8.0-openjdk"])

def main():
    
    parser = argparse.ArgumentParser(description="usage: %prog [options]")

    parser.add_argument("--downloadURL",
                      dest="downloadURL",
                      required=True,
                      help="Download URL for the Cycle install")

    parser.add_argument("--licenseURL",
                      dest="licenseURL",
                      help="Download URL for trial license")

    parser.add_argument("--cycleserverPW",
                      dest="cycleserverPW",
                      help="Admin password for CycleCloud server")

    parser.add_argument("--tenantId",
                      dest="tenantId",
                      help="Tenant ID of the Azure subscription")

    parser.add_argument("--applicationID",
                      dest="applicationID",
                      help="Application ID of the Service Principal")

    parser.add_argument("--applicationSecret",
                      dest="applicationSecret",
                      help="Application Secret of the Service Principal")

    parser.add_argument("--cyclePortalAccount",
                      dest="cyclePortalAccount",
                      help="Email address of the account in the CycleCloud portal for checking out licenses")

    parser.add_argument("--cyclePortalPW",
                      dest="cyclePortalPW",
                      help="Password for the ccount in the CycleCloud portal")

    args = parser.parse_args()

    installPreReq()
    downloadAndInstallCC(args) 
    ccLicense()
    generateSSHkey()
    modifyCSConfig()
    startCC()



if __name__ == "__main__":
    main()




