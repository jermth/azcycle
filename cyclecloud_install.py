#!/usr/bin/python
# Prepare an Azure provider account for CycleCloud usage.
import argparse
import tarfile
import json
import re
from random import SystemRandom
from string import ascii_letters, ascii_lowercase, digits
from subprocess import call
from os import path, makedirs, chdir, fdopen, remove
from urllib2 import urlopen, Request
from urllib import urlretrieve
from shutil import rmtree, copy2, move
from tempfile import mkstemp, mkdtemp


tmpdir = mkdtemp()
print "Creating temp directory " + tmpdir + " for installing CycleCloud"
cycle_root = "/opt/cycle_server"

def clean_up():
    rmtree(tmpdir)    


def setup_azure_account(tenant_id, application_id, application_secret, cycle_portal_account, cycle_portal_pw, cyclecloud_admin_pw):
    metadata_url = "http://169.254.169.254/metadata/instance?api-version=2017-08-01"
    metadata_req = Request(metadata_url, headers={"Metadata" : True})
    metadata_response = urlopen(metadata_req)
    vm_metadata = json.load(metadata_response)

    subscription_id = vm_metadata["compute"]["subscriptionId"]
    location = vm_metadata["compute"]["location"]
    resource_group = vm_metadata["compute"]["resourceGroupName"]

    random_suffix = ''.join(SystemRandom().choice(ascii_lowercase + digits) for _ in range(8))

    non_alphanu = re.compile('[\W_]+')
    storage_account_name = non_alphanu.sub('',resource_group).lower()  + random_suffix 

    azure_data = {
        "Name": "azure",
        "DefaultAccount": True,
        "Provider": "azure",
        "AzureRMSubscriptionId": subscription_id,
        "AzureRMTenantId": tenant_id,
        "AzureRMApplicationId": application_id,
        "AzureRMApplicationSecret": application_secret,
        "ProviderId": subscription_id,
        "AzureDefaultRegion": location,
        "AzureResourceGroup": resource_group,
        "RMStorageAccount": storage_account_name,
        "RMStorageContainer": "cyclecloud"
    }

    app_setting_data = {
        "AdType": "Application.Setting",
        "Name": "cycleserver.sendAnonymizedData",
        "Value": True
    }
    app_setting_installation = {
        "AdType": "Application.Setting",
        "Name": "cycleserver.installation.complete",
        "Value": True
    }
    authenticated_user = {
        "AdType": "AuthenticatedUser",
        "Name": "admin",
        "RawPassword": cyclecloud_admin_pw,
        "Superuser": True
    }
    site_name = {
        "AdType": "Application.Setting",
        "Name": "site_name",
        "Value": resource_group,
        "Category": "Support" 
    }
    portal_account = {
        "AdType": "Application.Setting",
        "Description": "The account login for this installation",
        "Value": cycle_portal_account,
        "Name": "support.account.login"
    }
    portal_login = {
        "AdType": "Application.Setting",
        "Description": "The account login for this installation",
        "Value": cycle_portal_pw,
        "Name": "support.account.password"
    }

    account_data = [
        app_setting_data,
        app_setting_installation,
        authenticated_user,        
        site_name,
        portal_account,
        portal_login 
    ]

    account_data_file = tmpdir + "/account_data.json"
    azure_data_file = tmpdir + "/azure_data.json"

    with open(account_data_file, 'w') as fp:
        json.dump(account_data, fp)

    with open(azure_data_file, 'w') as fp:
        json.dump(azure_data, fp)

    copy2(account_data_file, cycle_root + "/config/data/")

    call(["/usr/local/bin/cyclecloud", "initialize", "--batch", "--url=https://localhost", "--verify-ssl=false", "--username=admin", "--password=" + "'" + cyclecloud_admin_pw + "'" ])    

    homedir = path.expanduser("~")
    cycle_config = homedir + "/.cycle/config.ini"
    with open(cycle_config, "a") as config_file:
        config_file.write("\n")
        config_file.write("[pogo azure-storage]")
        config_file.write("type = az")
        config_file.write("subscription_id = " + subscription_id)
        config_file.write("tenant_id = " + tenant_id)
        config_file.write("application_id = " + application_id)
        config_file.write("application_secret = " + application_secret)
        config_file.write("matches = az://"+ storage_account_name + "/cyclecloud") 


def start_cc():
    cs_cmd = cycle_root + "/cycle_server"
    call([cs_cmd, "start"])
    call([cs_cmd, "await_startup"])
    call([cs_cmd, "status"])

def _sslCert(randomPW):
    call(["/bin/keytool", "-genkey", "-alias", "CycleServer", "-keypass", randomPW, "-keystore", cycle_root + "/.keystore", "-storepass", randomPW, "-keyalg", "RSA", "-noprompt", "-dname", "CN=cycleserver.azure.com,OU=Unknown, O=Unknown, L=Unknown, ST=Unknown, C=Unknown"])
    call(["chown", "cycle_server.", cycle_root+"/.keystore"])
    call(["chmod", "600", cycle_root+"/.keystore" ])


def modify_cs_config():
    # modify the CS config files
    cs_config_file = cycle_root + "/config/cycle_server.properties"

    randomPW = ''.join(SystemRandom().choice(ascii_letters + digits) for _ in range(16))
    # generate a self-signed cert
    _sslCert(randomPW)

    fh, tmp_cs_config_file = mkstemp()
    with fdopen(fh,'w') as new_config:
        with open(cs_config_file) as cs_config:
            for line in cs_config:
                if 'webServerMaxHeapSize=' in line:
                    new_config.write('webServerMaxHeapSize=4096M')
                elif 'webServerPort=' in line:
                    new_config.write('webServerPort=80')
                elif 'webServerSslPort=' in line:
                    new_config.write('webServerSslPort=443')
                elif 'webServerEnableHttps=' in line:
                    new_config.write('webServerEnableHttps=true')
                elif 'webServerKeystorePass=' in line:
                    new_config.write('webServerKeystorePass=' + randomPW)
                else:
                    new_config.write(line)

    remove(cs_config_file)
    move(tmp_cs_config_file, cs_config_file)

    #Ensure that the files are created by the cycleserver service user
    call(["chown", "-R", "cycle_server.", cycle_root])


def generate_ssh_key():
    # create an SSH private key for VM access
    homedir = path.expanduser("~")
    sshdir = homedir + "/.ssh"
    if not path.isdir(sshdir):
        makedirs(sshdir, mode=700) 
    
    sshkeyfile = sshdir + "/cyclecloud.pem"
    if not path.isfile(sshkeyfile):
        call(["ssh-keygen", "-f", sshkeyfile, "-t", "rsa", "-b", "2048","-P", ''])

    # make the cyclecloud.pem available to the cycle_server process
    cs_sshdir = cycle_root + "/.ssh"
    cs_sshkeyfile = cs_sshdir + "/cyclecloud.pem"

    if not path.isdir(cs_sshdir):
        makedirs(cs_sshdir, mode=700)
    
    if not path.isdir(cs_sshkeyfile):
        copy2(sshkeyfile, cs_sshkeyfile)
        call(["chown", "-R", "cycle_server.", cs_sshdir])


def cc_license(license_url):
    # get a license
    license_file = cycle_root + '/license.dat'
    print "Fetching temporary license from " + license_url
    urlretrieve(license_url, license_file)
    call(["chown", "cycle_server.", license_file])


def download_install_cc(download_url):    
    chdir(tmpdir)
    cc_url = download_url + "/cycle_server-all-linux64.tar.gz"
    cli_url = download_url + "/cyclecloud-cli.linux64.tar.gz"
    pogo_url = download_url + "/pogo-cli.linux64.tar.gz"

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
    copy2("cyclecloud", "/usr/local/bin")

    pogo_tar = tarfile.open("pogo-cli.linux64.tar.gz", "r:gz")
    pogo_tar.extractall(path=tmpdir)
    pogo_tar.close()
    copy2("pogo", "/usr/local/bin")

    call(["cycle_server/install.sh", "--nostart"])


def install_pre_req():
    call(["yum", "install", "-y", "java-1.8.0-openjdk"])

def main():
    
    parser = argparse.ArgumentParser(description="usage: %prog [options]")

    #debug 
    args = parser.parse_args()
    print("Debugging arguments: " + args)

    parser.add_argument("--downloadURL",
                      dest="downloadURL",
                    #   required=True,
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

    parser.add_argument("--applicationId",
                      dest="applicationId",
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

    parser.add_argument("--cyclecloudAdminPW",
                      dest="cyclecloudAdminPW",
                      help="Admin user password for the cyclecloud application server")

    args = parser.parse_args()

    install_pre_req()
    download_install_cc(args.downloadURL) 
    generate_ssh_key()
    modify_cs_config()
    cc_license(args.licenseURL)
    setup_azure_account(args.tenantId, args.applicationId, args.applicationSecret, args.cyclePortalAccount, args.cyclePortalPW, args.cyclecloudAdminPW)
    start_cc()
    setup_pogo_config()

    clean_up()


if __name__ == "__main__":
    main()




