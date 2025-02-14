#!/usr/bin/env python
"""
  Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.

  Permission is hereby granted, free of charge, to any person obtaining a copy of this
  software and associated documentation files (the "Software"), to deal in the Software
  without restriction, including without limitation the rights to use, copy, modify,
  merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
  permit persons to whom the Software is furnished to do so.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
  INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
  PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
  HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
  OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
  SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

"""
    Updates our dynamic patches from SSM data
    This script requires Boto3 and Credentials to call the SSM API
"""
import requests
import boto3
import json
import logging
from cfnlint.maintenance import SPEC_REGIONS

LOGGER = logging.getLogger('cfnlint')

region_map = {
    'US East (N. Virginia)': 'us-east-1',
    'Asia Pacific (Mumbai)': 'ap-south-1',
    'US East (Ohio)': 'us-east-2',
    'US West (Oregon)': 'us-west-2',
    'AWS GovCloud (US-East)': 'us-gov-east-1',
    'Asia Pacific (Hong Kong)': 'ap-east-1',
    'Asia Pacific (Tokyo)': 'ap-northeast-1',
    'EU (Stockholm)': 'eu-north-1',
    'Asia Pacific (Singapore)': 'ap-southeast-1',
    # 'Asia Pacific (Osaka-Local)': 'ap-northeast-3',
    'EU (London)': 'eu-west-2',
    'South America (Sao Paulo)': 'sa-east-1',
    'Asia Pacific (Sydney)': 'ap-southeast-2',
    'EU (Ireland)': 'eu-west-1',
    'EU (Frankfurt)': 'eu-central-1',
    'EU (Paris)': 'eu-west-3',
    'Canada (Central)': 'ca-central-1',
    'Asia Pacific (Seoul)': 'ap-northeast-2',
    'AWS GovCloud (US)': 'us-gov-west-1',
    'US West (N. California)': 'us-west-1',
}

exclude_regions = {
    'China (Beijing)': 'cn-north-1',
    'China (Ningxia)': 'cn-northwest-1',
    'Asia Pacific (Osaka-Local)': 'ap-northeast-3',
}

service_map = {
    'acm': ['AWS::CertificateManager::'],
    'apigateway': ['AWS::ApiGateway::', 'AWS::ApiGatewayV2::'],
    'application-autoscaling': ['AWS::ApplicationAutoScaling::'],
    'appstream': ['AWS::AppStream::'],
    'appsync': ['AWS::AppSync::'],
    'athena': ['AWS::Athena::'],
    'autoscaling': ['AWS::AutoScaling::'],
    'batch': ['AWS::Batch::'],
    'budgets': ['AWS::Budgets::'],
    'cloud9': ['AWS::Cloud9::'],
    'cloudfront': ['AWS::CloudFront::'],
    'cloudtrail': ['AWS::CloudTrail::'],
    'cloudwatch': ['AWS::CloudWatch::'],
    'codebuild': ['AWS::CodeBuild::'],
    'codecommit': ['AWS::CodeCommit::'],
    'codedeploy': ['AWS::CodeDeploy::'],
    'codepipeline': ['AWS::CodePipeline::'],
    'cognito-identity': ['AWS::Cognito::'],
    'config': ['AWS::Config::'],
    'datapipeline': ['AWS::DataPipeline::'],
    'dax': ['AWS::DAX::'],
    'dms': ['AWS::DMS::'],
    'docdb': ['AWS::DocDB::'],
    'ds': ['AWS::DirectoryService::'],
    'dynamodb': ['AWS::DynamoDB::'],
    'ec2': ['AWS::EC2::'],
    'ecr': ['AWS::ECR::'],
    'ecs': ['AWS::ECS::'],
    'efs': ['AWS::EFS::'],
    'eks': ['AWS::EKS::'],
    'elasticache': ['AWS::ElastiCache::'],
    'elasticbeanstalk': ['AWS::ElasticBeanstalk::'],
    'elb': ['AWS::ElasticLoadBalancing::', 'AWS::ElasticLoadBalancingV2::'],
    'emr': ['AWS::EMR::'],
    'es': ['AWS::Elasticsearch::'],
    'events': ['AWS::Events::'],
    'firehose': ['AWS::KinesisFirehose::'],
    'fsx': ['AWS::FSx::'],
    'gamelift': ['AWS::GameLift::'],
    'glue': ['AWS::Glue::'],
    'greengrass': ['AWS::Greengrass::'],
    'guardduty': ['AWS::GuardDuty::'],
    'inspector': ['AWS::Inspector::'],
    'iot': ['AWS::IoT::'],
    'iot1click-projects': ['AWS::IoT1Click::'],
    'iotanalytics': ['AWS::IoTAnalytics::'],
    'kinesis': ['AWS::Kinesis::'],
    'kinesisanalytics': ['AWS::KinesisAnalytics::', 'AWS::KinesisAnalyticsV2::'],
    'kms': ['AWS::KMS::'],
    'lambda': ['AWS::Lambda::'],
    'logs': ['AWS::Logs::'],
    'mq': ['AWS::AmazonMQ::'],
    'neptune': ['AWS::Neptune::'],
    'opsworks': ['AWS::OpsWorks::'],
    'opsworkscm': ['AWS::OpsWorksCM::'],
    'ram': ['AWS::RAM::'],
    'rds': ['AWS::RDS::'],
    'redshift': ['AWS::Redshift::'],
    'robomaker': ['AWS::RoboMaker::'],
    'route53': ['AWS::Route53::'],
    'route53resolver': ['AWS::Route53Resolver::ResolverRule', 'AWS::Route53Resolver::ResolverEndpoint'],
    's3': ['AWS::S3::'],
    'sagemaker': ['AWS::SageMaker::'],
    'sdb': ['AWS::SDB::'],
    'secretsmanager': ['AWS::SecretsManager::'],
    'servicecatalog': ['AWS::ServiceCatalog::'],
    'servicediscovery': ['AWS::ServiceDiscovery::'],
    'ses': ['AWS::SES::'],
    'sns': ['AWS::SNS::'],
    'sqs': ['AWS::SQS::'],
    'ssm': ['AWS::SSM::'],
    'stepfunctions': ['AWS::StepFunctions::'],
    'waf-regional': ['AWS::WAFRegional::'],
    'workspaces': ['AWS::WorkSpaces::'],
}

session = boto3.session.Session()
client = session.client('ssm', region_name='us-east-1')


def configure_logging():
    """Setup Logging"""
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    LOGGER.setLevel(logging.INFO)
    log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(log_formatter)

    # make sure all other log handlers are removed before adding it back
    for handler in LOGGER.handlers:
        LOGGER.removeHandler(handler)
    LOGGER.addHandler(ch)


def update_outputs(region, resource_type, name, outputs):
    """ update outputs with appropriate results """
    element = {
        "op": "remove",
        "path": "/%s/%s" % (resource_type, name)
    }
    outputs[region].append(element)

    return outputs


def get_all_regions():
    """ get a list of all the regions """
    results = []
    for region in region_map.values():
        results.append(region)
    return results


def get_regions_for_service(service):
    """ get regions for a service """
    LOGGER.info('Get the regions for service %s', service)
    results = []
    paginator = client.get_paginator('get_parameters_by_path')
    page_iterator = paginator.paginate(
        Path='/aws/service/global-infrastructure/services/{}/regions'.format(service),
    )

    for page in page_iterator:
        for region in page.get('Parameters'):
            results.append(region.get('Value'))

    return results


def add_spec_patch(region, services):
    """ Go through spec and determine patching """
    LOGGER.info('Create 06_ssm_service_removal patch for region %s', region)
    req = requests.get(SPEC_REGIONS.get(region))

    spec = json.loads(req.content.decode('utf-8'))

    patches = []

    for spec_type in ['ResourceTypes', 'PropertyTypes']:
        for resource in sorted(spec.get(spec_type).keys()):
            for service in services:
                for spec_name in service_map.get(service):
                    if resource.startswith(spec_name):
                        element = {
                            'op': 'remove',
                            'path': '/%s/%s' % (spec_type, resource)
                        }
                        patches.append(element)

    filename = 'src/cfnlint/data/ExtendedSpecs/%s/06_ssm_service_removal.json' % region
    with open(filename, 'w+') as f:
        json.dump(patches, f, indent=2, sort_keys=True, separators=(',', ': '))


def add_spec_missing_services_patch(region, services):
    """ Go through spec and determine patching """
    LOGGER.info('Create 07_ssm_service_addition patch for region %s', region)
    req = requests.get(SPEC_REGIONS.get(region))
    req_standard = requests.get(SPEC_REGIONS.get('us-east-1'))

    spec = json.loads(req.content.decode('utf-8'))
    spec_standard = json.loads(req_standard.content.decode('utf-8'))

    patches = []

    for spec_type in ['ResourceTypes']:
        for service in services:
            found = False
            for resource in sorted(spec.get(spec_type).keys()):
                for spec_name in service_map.get(service):
                    if resource.startswith(spec_name):
                        found = True
            if found is False:
                for standard_spec_type in ['ResourceTypes', 'PropertyTypes']:
                    for resource in sorted(spec_standard.get(standard_spec_type).keys()):
                        for spec_name in service_map.get(service):
                            if resource.startswith(spec_name):
                                if spec_standard.get(spec_type).get(resource):
                                    element = {
                                        'op': 'add',
                                        'path': '/%s/%s' % (spec_type, resource),
                                        'value': spec_standard.get(spec_type).get(resource)
                                    }
                                    patches.append(element)
                                elif standard_spec_type == 'ResourceTypes':
                                    print('patch for %s not found' % service)

    if patches:
        filename = 'src/cfnlint/data/ExtendedSpecs/%s/07_ssm_service_addition.json' % region
        with open(filename, 'w+') as f:
            json.dump(patches, f, indent=2, sort_keys=True, separators=(',', ': '))


def main():
    """ main function """
    configure_logging()

    all_regions = get_all_regions()
    region_service_removal_map = {}
    region_service_add_map = {}
    for region in all_regions:
        region_service_removal_map[region] = []
        region_service_add_map[region] = []
    for service in service_map:
        regions = get_regions_for_service(service)
        if regions:
            for region in list(set(regions) - set(exclude_regions.values())):
                region_service_add_map[region].append(service)
            for region in list(set(all_regions) - set(regions)):
                region_service_removal_map[region].append(service)

    for region, services in region_service_removal_map.items():
        if services:
            add_spec_patch(region, services)
    for region, services in region_service_add_map.items():
        if services:
            add_spec_missing_services_patch(region, services)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, TypeError):
        LOGGER.error(ValueError)
