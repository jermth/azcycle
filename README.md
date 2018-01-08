# azcycle
Cycle Server on Azure scripts and templates


## Create network
<a href="https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fjermth%2Fazcycle%2Fmaster%2Fdeploy-vnet.json" target="_blank">
    <img src="http://azuredeploy.net/deploybutton.png" />
</a>

## Create cycle server
<a href="https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fjermth%2Fazcycle%2Fmaster%2Fdeploy-vms.json" target="_blank">
    <img src="http://azuredeploy.net/deploybutton.png" />
</a>





## Pre-requisites
1. [Azure CLI 2.0](https://docs.microsoft.com/en-us/cli/azure/overview?view=azure-cli-latest) installed and configured with an Azure subscription

2. [Service principal in your Azure Active Directory](https://docs.microsoft.com/en-us/cli/azure/create-an-azure-service-principal-azure-cli?view=azure-cli-latest)

Essentially:
```

        $ az ad sp create-for-rbac --name CycleCloudApp --years 1

Save the output -- you'll need the appId, password and tenant id.
        {
                "appId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                "displayName": "CycleCloudApp",
                "name": "http://CycleCloudApp",
                "password": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                "tenant": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        }
```
3. Azure subscription ID. 

The easiest way to retrieve it:
```
        $ az account list -o table
```


## Create Azure Resources

* Clone the repo 

        git clone https://github.com/{githubuser}/azcycle.git

* Edit vms-params.json:
    * You need to update three parameters: `cycleDownloadUri`, `cycleLicenseURL`, and `rsaPublicKey`
    * Obtain `cycleDownloadUri` and `cycleLicenseURL` from your Cycle team contact.
    * `rsaPublicKey` is the SSH public key corresponding to the private key you will use to log into the VMs.

* Create a resource group in the region of your choice:

        az group create --name "{RESOURCE-GROUP}" --location "{REGION}"

* Build the Virtual Network and subnets. By default the vnet is named **cyclevnet** . Update the **{githubuser}** value with your github user name

        az group deployment create --name "vnet_deployment" --resource-group "{RESOURCE-GROUP}" --template-uri https://raw.githubusercontent.com/{githubuser}/azcycle/master/deploy-vnet.json --parameters vnet-params.json

* Build the VMs. Update the **{githubuser}** value with your github user name

        az group deployment create --name "vms_deployment" --resource-group "{RESOURCE-GROUP}" --template-uri https://raw.githubusercontent.com/{githubuser}/azcycle/master/deploy-vms.json --parameters vms-params.json


## Configure CycleCloud Server through the Webserver

* To connect to the CycleCloud webserver, first retrieve the FQDN of the CycleServer VM from the Azure Portal, then browse to https://cycleserverfqdn/. The installation uses a self-signed SSL certificate which may show up with a warning in your browser.

* This installation comes with a temporary license. 

* When you first log into the CycleCloud webserver and it asks for a Cycle Computing account, ignore and click on **Next** if you do not have an account.

![Account Setup](https://docs.cyclecomputing.com/wp-content/uploads/2017/10/setup-step1.png)


## Setting up CycleCloud with an Azure Subscription
* Click on Clusters in the top menu bar. A notice will appear that you currently do not have a cloud provider set up.

![Add CSP](https://docs.cyclecomputing.com/wp-content/uploads/2017/10/no_accounts_found.png)

* Click the link to add your subscription.

![Configure Subscription](https://docs.cyclecomputing.com/wp-content/uploads/2017/10/create_azure.png)

* From the drop-down, select Microsoft Azure as the provider. Enter the Subscription ID, Tenant ID, Application ID, and Application Secret. If you do now have these, look at the **Pre-requisites** section above on instructions to retrieve these. The service principal password is the **Application Secret**. 

* Add the Storage Account and Storage Container to use for storing configuration and application data for your cluster. If it does not already exist, the container will be created.

* Check the “Set Default” option to make this azure subscription the default. Once you have completed setting the parameters for your Azure account, click Save to continue.


## Setup CycleCloud CLI
* The CycleCloud CLI is required for importing custom cluster templates, and is installed in the **cycleserver** VM. SSH access into this VM is not directly accessible -- you have to first SSH into the admin jumpbox to reach it.

* In the Azure portal, retrieve the full DNS name of the admin jump box. You can then SSH on it with the **cycleadmin** user with the SSH key you provided. Once on the jumbox

        $ ssh cycleserver

* Initialize CycleCloud CLI

        $ cyclecloud initialize


## Check installation logs

* The Cycle Server installation logs are located in the /var/lib/waagent/custom-script/download/0 directory.

# Create your cluster

* Build your cluster in Cycle by using the provided templates

