# CentralizedRestoreEC2ViaBackupSerivce

## 简介
通过输入标签，过滤匹配的EC2资源，并且进行集中回复AWS Backup 服务自动化批量恢复，最后会带过去原始标签。

#### 注意： 

* Region, AvailabilityZone, VPCId, SubnetId,  SecurityGroupIds 必须保证它们匹配，不然会导致整个恢复过程失败。

* 恢复失败后，请查找执行日志里面的resotreJobId，然后去对应界面查找失败的原因，进行调整。

* 恢复失败不会导致你的备份数据丢失

* 这个资源选择备份目标的方式有两种: Tags和Arn，基于最佳实践认为Tags比较符合实际场景，故使用的是基于Tags的恢复。

* 未来会支持更多的服务，包括但不限于： rds, ebs, efs 等等

* 目前只支持最新时间点的恢复，如果需要精细粒度的恢复，请采用手工方式。

---

## 参数:

**AutomationAssumeRole** :  建议参考 [使用 IAM 为自动化配置角色] (https://docs.aws.amazon.com/zh_cn/systems-manager/latest/userguide/automation-setup-iam.html) 来创建运行的role。需要至少 *AmazonSSMAutomationRole*, *AWSBackupFullAccess*, *AWSBackupServiceRolePolicyForRestores*, *AWSBackupServiceRolePolicyForBackup* 的权限，trust relationships设置为：
```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "",
            "Effect": "Allow",
            "Principal": {
                "Service": ["ssm.amazonaws.com", "backup.amazonaws.com"]
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
```
**FilterTags**：过滤用的标签，比如"Patcher:benxiwan"

**ValutName**:  backup服务对应的Valut名字，默认为Default

**VPCId**: 需要恢复到的VPC, 比如*vpc-05700587b55d89574*

**SubnetId**：需要恢复到的子网, 比如*subnet-02ac249be70cb17f8*

**SecurityGroupIds** 用逗号分割的安全组(e.g. sg-xxxxxx, sg-yyyyy). 用逗号分割的安全组(e.g. sg-xxxxxx, sg-yyyyy). 如果没有指定，且在同一个区域，会沿用目前的安全组；如果去了另外一个区域， 则会使用default安全组

**AvailabilityZone**  需要恢复到哪个AZ， 比如*us-east-1b*

**Region** 是否需要更换区域, 比如*us-east-1*

**PreservePrivateIp** 是否需要保持原来的私有ip，默认为false；如果选择了true, 确保vpc的ip段正确，以及相应的ip没有被占用

---

## 返回：

**resJobIds** 恢复job id

**resourceIds** 恢复成功的实例

