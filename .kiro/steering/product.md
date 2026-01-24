# TANGO Multi-Agent Pipeline

TANGO is an automated system that validates AWS CloudControl (AWSCC) Terraform resources through real-world deployment testing. It discovers unprocessed AWS resources from GitHub releases, generates Terraform configurations, deploys them to actual AWS environments, and produces production-ready examples with comprehensive analysis.

## Core Purpose

Addresses the critical gap in AWS CloudControl documentation by providing validated, working Terraform examples that have been tested against live AWS infrastructure.

## Key Capabilities

- Automated discovery of new AWSCC resources from HashiCorp GitHub releases
- AI-powered Terraform code generation using AWS documentation
- Real AWS deployment validation (apply/destroy lifecycle)
- Independent validation and quality assessment
- Automated storage of results in DynamoDB and S3
- Cleanup of orphaned AWS resources

## Target Audience

Developers and infrastructure teams working with AWS CloudControl and Terraform who need reliable, tested configuration examples.
