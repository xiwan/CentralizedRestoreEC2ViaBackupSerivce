import boto3
import json
import random
import time

def describe_restore_job(restore):
  return client.describe_restore_job(
  	RestoreJobId = restore['RestoreJobId']
  )

ValidType = 'EC2'
client = boto3.client('backup')

def match_tags(resourceArn, filterTag):
  Key = filterTag.split(":")[0]
  Value = filterTag.split(":")[1]

  points = client.list_recovery_points_by_resource(
    ResourceArn=resourceArn
  )
  recoveryPoint = ''
  recoveryTags = {}

  # find the latest recovery point
  for point in points['RecoveryPoints']:
    if point['Status'] == 'COMPLETED':
      tags = client.list_tags(
        ResourceArn=point['RecoveryPointArn']
      )
      recoveryPoint = point['RecoveryPointArn']
      recoveryTags = tags['Tags']

      filter = False
      for k,v in recoveryTags.items() :
        if k == Key and v == Value :
          filter = True
      # filter out by the tags
      if not filter :
        recoveryTags = {}
        recoveryPoint = ''
      if filter:
        break

  return (recoveryPoint, recoveryTags)

def meta_modifier(events, metadata):
  Region = events['Region']
  AutomationAssumeRole = events['AutomationAssumeRole']
  # ResourceArn = events['ResourceArn']
  ValutName = events['ValutName']
  # InstanceType = events['InstanceType']
  VPCId = events['VPCId']
  SubnetId = events['SubnetId']
  AvailabilityZone = events['AvailabilityZone']
  SecurityGroupIds = events['SecurityGroupIds']
  PreservePrivateIp = events['PreservePrivateIp']
  # PrivateIpAddress = events['PrivateIpAddress']

  # print(json.dumps(metadata['RestoreMetadata'], indent=2))

  # 修改vpcid
  if VPCId != '':
    metadata['RestoreMetadata']['VpcId'] =  VPCId
  # 修改AZ
  if AvailabilityZone != '':
    Placement = json.loads(metadata['RestoreMetadata']['Placement'])
    Placement['AvailabilityZone'] = AvailabilityZone
    metadata['RestoreMetadata']['Placement'] = json.dumps(Placement)
  # 修改InstanceType
  # if InstanceType != '':
  #   metadata['RestoreMetadata']['InstanceType'] =  InstanceType
      
  # 修改网络配置部分
  networkInterfaces = json.loads(metadata['RestoreMetadata']['NetworkInterfaces'])
  for interface in networkInterfaces:
    # The associatePublicIPAddress parameter cannot be specified for a network interface with an ID.
    del interface['AssociatePublicIpAddress']
    # A network interface may not specify both a network interface ID and a subnet
    del interface['NetworkInterfaceId']
    # Only one primary private IP address can be specified.
    del interface['PrivateIpAddress']

    # 修改子网id
    if SubnetId != '':
      interface['SubnetId'] = SubnetId

    # 修改安全组
    if SecurityGroupIds != '':
      interface['Groups'] = SecurityGroupIds.split(",")
    else:
      ec2client = boto3.client('ec2', region_name=Region)
      data = ec2client.describe_security_groups(
        Filters=[
          {
              'Name': 'vpc-id', 'Values': [VPCId]
          },
          {
              'Name': 'group-name', 'Values': ["default"]
          }
        ]
      )
      interface['Groups'] = [data["SecurityGroups"][0]["GroupId"]]

    # # 修改私有地址
    # if PrivateIpAddress != '':
    #   for ipaddress in interface['PrivateIpAddresses']:
    #     if ipaddress['Primary'] is True:
    #       ipaddress['PrivateIpAddress'] = PrivateIpAddress
    #       break
    # else:
    # # 随机私有地址
    #   del interface['PrivateIpAddresses']

    if PreservePrivateIp:
      for ipaddress in interface['PrivateIpAddresses']:
        if ipaddress['Primary'] is True:
          print(ipaddress['PrivateIpAddress'])
          break
      pass
    else:
      # 删除私有地址
      del interface['PrivateIpAddresses']
      pass
          
    # Value (0) for parameter secondaryPrivateIpAddressCount is invalid. Value must be a positive number.
    interface['secondaryPrivateIpAddressCount'] = 1
    break

  metadata['RestoreMetadata']['NetworkInterfaces'] = json.dumps(networkInterfaces)

  insType = metadata['RestoreMetadata']['InstanceType'] 
  # print(insType)
  if insType.startswith( 't' ):
    # t 系列需要保留
    metadata['RestoreMetadata']['CreditSpecification'] = json.dumps({'CpuCredits': 'standard'})
    del metadata['RestoreMetadata']['CpuOptions']
  else:
    # 非 t 系列
    # del metadata['RestoreMetadata']['CpuOptions']
    pass

  # 去掉不需要的字段
  del metadata['RestoreMetadata']['IamInstanceProfileName']
  del metadata['RestoreMetadata']['SecurityGroupIds']
  del metadata['RestoreMetadata']['SubnetId']

  # print(recoveryPoint)
  # print(type(metadata['RestoreMetadata']))
  # print(json.dumps(metadata['RestoreMetadata'], indent=2))

  pass


def script_handler(events, context):
  Region = events['Region']
  AutomationAssumeRole = events['AutomationAssumeRole']
  FilterTags = events['FilterTags']
  ValutName = events['ValutName']
  # InstanceType = events['InstanceType']
  VPCId = events['VPCId']
  SubnetId = events['SubnetId']
  AvailabilityZone = events['AvailabilityZone']
  SecurityGroupIds = events['SecurityGroupIds']
  PreservePrivateIp = events['PreservePrivateIp']
  # PrivateIpAddress = events['PrivateIpAddress']
  
  print(AutomationAssumeRole)

  # create service client using the assumed role credentials, e.g. S3
  client = boto3.client('backup', region_name=Region)

  RestoreJobIds = []
  recoveryTags = {}
  resources = client.list_protected_resources()
  for res in resources['Results'] :
    # only support EC2 now

    if res['ResourceType'] == ValidType :
      recoveryPoint, recoveryTag = match_tags(res['ResourceArn'], FilterTags)
      print(recoveryPoint)
      print(recoveryTag)

      if recoveryPoint == '' :
        print('recoveryPoint not exit')
        continue

      metadata = client.get_recovery_point_restore_metadata(
        BackupVaultName = ValutName,
        RecoveryPointArn = recoveryPoint
      )

      meta_modifier(events, metadata)
      # continue

      # start the restore job
      restore = client.start_restore_job(
        RecoveryPointArn = recoveryPoint,
        IamRoleArn = AutomationAssumeRole,
        Metadata = metadata['RestoreMetadata'],
        ResourceType = ValidType
      )
      RestoreJobIds.append(restore['RestoreJobId'])
      recoveryTags[restore['RestoreJobId']] = recoveryTag

      pass

  print(RestoreJobIds)
  print(recoveryTags)

  resourceIds = []
  resJobIds = []
  finishedJobs = [0] * len(RestoreJobIds)
  while True:
    for idx, resJobId in enumerate(RestoreJobIds):
      data = client.describe_restore_job(
        RestoreJobId = resJobId
      )

      if not recoveryTags[resJobId]:
        continue

      print(resJobId + '|' + data['Status'])
      if data['Status'] != 'PENDING' and data['Status'] != 'RUNNING' :
        pass

      if data['Status'] == 'COMPLETED' and data['CreatedResourceArn'] != '' and finishedJobs[idx] == 0:
        finishedJobs[idx] = 1
        print(recoveryTags[resJobId])
        Tags = []
        for k,v in recoveryTags[resJobId].items():
          if k.startswith("aws:"):
            continue
          tag = {'Key': k, 'Value': v}
          Tags.append(tag)
        print(Tags)

        resourceId = data['CreatedResourceArn'].split("/")[1]
        ec2client = boto3.client('ec2', region_name=Region)
        response = ec2client.create_tags(
          Resources = [resourceId],
          Tags = Tags
        )

        if not resourceId in resourceIds:
          print(resourceId)
          resourceIds.append(resourceId)
        if not resJobId in resJobIds:
          print(resJobId)
          resJobIds.append(resJobId)

    time.sleep(1)
    if sum(finishedJobs) == len(RestoreJobIds):
      break

  # print(resourceIds)
  return {'resourceIds': resourceIds, 'resJobId': resJobIds}

