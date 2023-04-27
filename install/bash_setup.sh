# Define SPARK_HOME and add to PATH
echo 'export SPARK_HOME=/usr/local/spark' >> ~/.bashrc
echo 'export PATH=$SPARK_HOME/bin:$PATH' >> ~/.bashrc
echo 'export SPARK_LOCAL_IP="127.0.0.1"' >> ~/.bashrc

# Define JAVA_HOME and add to PATH
echo 'export PATH=/usr/bin/java:$PATH' >> ~/.bashrc

#Add conda for user environment - even when ezj hasn't been run that session.
echo ". /opt/anaconda3/etc/profile.d/conda.sh" >> ~/.bashrc
#This makes conda activate available.
