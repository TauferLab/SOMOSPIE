# https://cloud.ibm.com/docs/cloud-object-storage/libraries?topic=cloud-object-storage-python#python-examples-multipart
import ibm_boto3
from ibm_botocore.client import Config, ClientError
import subprocess
import json

# Constants for IBM COS values
COS_ENDPOINT = "https://s3.us-east.cloud-object-storage.appdomain.cloud" # Current list avaiable at https://control.cloud-object-storage.cloud.ibm.com/v2/endpoints
COS_API_KEY_ID = "cEukYcgxuaNRNpGmoaKZGhODEu9Qlh79UBPbSFr8H77l" # eg "W00YixxxxxxxxxxMB-odB-2ySfTrFBIQQWanc--P3byk"
COS_INSTANCE_CRN = "crn:v1:bluemix:public:iam-identity::a/dc12111b99cf4ec789ef525521b980ef::serviceid:ServiceId-b1c4462c-593f-44e8-bdbb-cf4da28761b7" # eg "crn:v1:bluemix:public:cloud-object-storage:global:a/3bf0d9003xxxxxxxxxx1c3e97696b71c:d6f04d83-6c4f-4a62-a165-696756d63903::"

# Create resource
cos = ibm_boto3.resource("s3",
    ibm_api_key_id=COS_API_KEY_ID,
    ibm_service_instance_id=COS_INSTANCE_CRN,
    config=Config(signature_version="oauth"),
    endpoint_url=COS_ENDPOINT
)


def get_buckets():
    print("Retrieving list of buckets")
    try:
        buckets = cos.buckets.all()
        for bucket in buckets:
            print("Bucket Name: {0}".format(bucket.name))
    except ClientError as be:
        print("CLIENT ERROR: {0}\n".format(be))
    except Exception as e:
        print("Unable to retrieve list buckets: {0}".format(e))

        
def get_bucket_contents(bucket_name):
    print("Retrieving bucket contents from: {0}".format(bucket_name))
    try:
        files = cos.Bucket(bucket_name).objects.all()
        for file in files:
            print("Item: {0} ({1} bytes).".format(file.key, file.size))
    except ClientError as be:
        print("CLIENT ERROR: {0}\n".format(be))
    except Exception as e:
        print("Unable to retrieve bucket contents: {0}".format(e))
        
        
def multi_part_upload(bucket_name, item_name, file_path):
    try:
        print("Starting file transfer for {0} to bucket: {1}\n".format(item_name, bucket_name))
        # set 5 MB chunks
        part_size = 1024 * 1024 * 5

        # set threadhold to 15 MB
        file_threshold = 1024 * 1024 * 15

        # set the transfer threshold and chunk size
        transfer_config = ibm_boto3.s3.transfer.TransferConfig(
            multipart_threshold=file_threshold,
            multipart_chunksize=part_size
        )

        # the upload_fileobj method will automatically execute a multi-part upload
        # in 5 MB chunks for all files over 15 MB
        with open(file_path, "rb") as file_data:
            cos.Object(bucket_name, item_name).upload_fileobj(
                Fileobj=file_data,
                Config=transfer_config
            )

        print("Transfer for {0} Complete!\n".format(item_name))
    except ClientError as be:
        print("CLIENT ERROR: {0}\n".format(be))
    except Exception as e:
        print("Unable to complete multi-part upload: {0}".format(e))
        
        
def download_file(bucket_name, item_name, file_path):
    # Create client 
    cos_client = ibm_boto3.client("s3",
        ibm_api_key_id=COS_API_KEY_ID,
        ibm_service_instance_id=COS_INSTANCE_CRN,
        config=Config(signature_version="oauth"),
        endpoint_url=COS_ENDPOINT
    )
    try:
        print("Starting file download for {0} to bucket: {1}\n".format(item_name, bucket_name))
        res=cos_client.download_file(Bucket=bucket_name,Key=item_name, Filename=file_path)
    except Exception as e:
        print(Exception, e)
    else:
        print('File Downloaded')


def bash(argv):
    arg_seq = [str(arg) for arg in argv]
    proc = subprocess.Popen(arg_seq)#, shell=True)
    proc.wait() #... unless intentionally asynchronous
        

def cancel_uploads(json_file, bucket_name): 
    # aws s3api list-multipart-uploads --bucket conus-10m --endpoint-url=https://s3.us-east.cloud-object-storage.appdomain.cloud > incomplete.json
    data = json.load(open(json_file))
    n_uploads = len(data['Uploads'])
    count = 1

    for id in data['Uploads']:
        print('Cancelling incomplete multi-part uploads... {} out of {}.'.format(count, n_uploads))
        cmd = ['aws', 's3api', 'abort-multipart-upload', '--bucket', bucket_name, '--endpoint-url=https://s3.us-east.cloud-object-storage.appdomain.cloud', '--key', id['Key'], '--upload-id', id['UploadId']]
        bash(cmd)
        count += 1

        
if __name__ == '__main__':
    #get_buckets()
    #get_bucket_contents('conus-10m')
    #multi_part_upload('conus-10m', 'CONUS_WGS84_10m_elevation.tif', '/media/volume/sdb/terrain_parameters/CONUS_10m/CONUS_WGS84_10m_elevation.tif')
    download_file('conus-10m', 'CONUS_WGS84_10m_elevation.tif', '/media/volume/sdb/terrain_parameters/CONUS_WGS84_10m_elevation.tif')
    
