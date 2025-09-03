Ask ai to refine plan.md
I want you to make this plan.md proper impleentation requirenment document. make sure there is proper requirements no and sub numbers are there with checkbox for each task.
Also write down to do 1 task at a time
Once its complete do testing yourslef with curl or whatever tesy is required.
If you want to create a new test file, make sure you create that in test directory.
make sure whole workspace is neat and clean




Create a new virtual phython envirnment if there is no .venv file in directory.

Project name: Adding new hosts to k8s cluster


Step1: 
Create Streamlit web page:
1.1: create a streamlit app which has a button called Test where user will enter the IP of the host he wants to add.

1.2: Above 'test' button, it should display :
Does this server meet minimum cluster requirements?

1.3: After user hits 'Test' button, run python program called: System.py


Step 2: 
create system.py
1.1: SSH to the host
1.2: Check if the host meets minimum server requirements to add this host to the cluster which are:
CPU = 
Memory =
Disk space = 


Step 3: 
If this host meets minimum system requirements go to step 3.1, else go to step 3.2
3.1: reply by displaying this: Congratulations, your host meets the minimum serevr requirements to be part of cluster.
3.2: Reply by displaying: Your host doesnt meet minimum server requirements to be part of cluster. Please make sure it should have following specifications:
 CPU = 
Memory =
Disk space = 


-----------

Step4:Once system.py is created, integrate it to the streamlit app we created in Step1

















