# AWS CLI Tracer

![Example Terminal Session](/termsession_example.svg?raw=true&sanitize=true)

## Usage

## Installation

Please note that this tool requires at least Python `>= 3.6`. To install from source simply clone the repository and run:

```
$ python setup.py sdist
$ pip install dist/awstracer-1.0.tar.gz
```

## Example 1: Creating a DynamoDB table and adding data to it

This is the example that can also be seen in the recorded terminal session above. Let's create a tracefile that creates a DynamoDB table named `Music` and inserts a song in the table. The commands are taken directly from the [Amazon DynamoDB Developer Guide](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/getting-started-step-1.html). This looks something like this. Please note that the output is truncated.

```
$ awstrace-rec --trace-file create_table.trace
(rec) aws dynamodb create-table \
>     --table-name Music \
>     --attribute-definitions \
>         AttributeName=Artist,AttributeType=S \
>         AttributeName=SongTitle,AttributeType=S \
>     --key-schema \
>         AttributeName=Artist,KeyType=HASH \
>         AttributeName=SongTitle,KeyType=RANGE \
> --provisioned-throughput \
>         ReadCapacityUnits=10,WriteCapacityUnits=5
[...]
Add command to trace cache? [y/N]: y
(rec) aws dynamodb put-item \
> --table-name Music  \
> --item \
>     '{"Artist": {"S": "No One You Know"}, "SongTitle": {"S": "Call Me Today"}, "AlbumTitle": {"S": "Somewhat Famous"}, "Awards": {"N": "1"}}'
Add command to trace cache? [y/N]: y
(rec)
Save cached trace to create_table.trace? [y/N]: y
```

Now we can simply replay our trace. If we play it we get the following error as the table already exists:

```
$ awstrace-play --trace-file create_table.trace
(play) aws dynamodb create-table --attribute-definitions '[{"AttributeName": "Artist", "AttributeType": "S"}, {"AttributeName": "SongTitle", "AttributeType": "S"}]' --key-schema '[{"AttributeName": "Artist", "KeyType": "HASH"}, {"AttributeName": "SongTitle", "KeyType": "RANGE"}]' --provisioned-throughput '{"ReadCapacityUnits": 10, "WriteCapacityUnits": 5}' --table-name Music

An error occurred (ResourceInUseException) when calling the CreateTable operation: Table already exists: Music
```

We can immediately run the trace against a different region, profile or endpoint. To do so we simply use the `--region`, `--profile` or `--endpoint` parameters similarly to how this works with the AWS CLI. For example to run the same trace under the `admin-profile` against the endpoint `https://beta-service-url.com` we can do the following:

```
$ awstrace-play --trace-file create_table.trace --profile admin-profile --endpoint https://beta-service-url.com
```

The player has the ability to automatically derive relationships between subsequent commands. This means that we have the ability to override a parameter inside a trace file without having to edit the trace file or edit any of the commands themselves. For example if we want to create a table with a different name but still want to get the data inserted to that new table we simply do this:

```
$ awstrace-play --trace-file create_table.trace --param table-name test-table
[...]
$ aws dynamodb list-tables
{
    "TableNames": [
        "Music",
        "test-table",
    ]
}
```

We can see that `test-table` was created. To check if the data actually got inserted we can use the following to see if we can get an item returned from the table. If that works it means the player did its job correctly and it replayed the trace with the overridden parameters properly.

```
$ aws dynamodb get-item --consistent-read --table-name bla-table --key '{ "Artist": {"S": "No One You Know"}, "SongTitle": {"S": "Call Me Today"}}
{
    "Item": {
        "AlbumTitle": {
            "S": "Somewhat Famous"
        },
        "Awards": {
            "N": "1"
        },
        "Artist": {
            "S": "No One You Know"
        },
        "SongTitle": {
            "S": "Call Me Today"
        }
    }
}
```

## Example 2: Creating AWS users and policies

We start a recording session. First we create user `test-user1`. We then create a policy from `file://policy.json` named `test-policy1` and subsequently attach the policy to the user.

```
$ awstrace-rec --trace-file create_user.trace
(rec) aws iam create-user --user-name test-user-1
[...]
(rec) aws iam create-policy --policy-name test-policy-1 --policy-document file://policy.json
{
    "Policy": {
    [...]
        "Arn": "arn:aws:iam::111111111111:policy/policy1",
    [...]
    }
}
(rec) aws iam attach-user-policy --user-name test-user-1 --policy-arn arn:aws:iam::111111111111:policy/policy1
[...]
aws iam list-attached-user-policies --user-name test-user-1
{
    "AttachedPolicies": [
        {
            "PolicyName": "policy1",
            "PolicyArn": "arn:aws:iam::111111111111:policy/policy1"
        }
    ]
}
```

To now create a different user with a different policy all we have to do is edit the `policy.json` file and then rerun the trace.
We can do a dry-run first by specifying `--dryrun` to see if the appropiate relations between the traces has been properly derived.
This will look something like this:

```
$ awstrace-play --trace-file create-user.trace --param user-name tu -user3 --param policy-name tp --param policy-document file://policy.json --dryrun
(play) aws iam create-user --user-name tu
(play) aws iam create-policy --policy-document file://policy.json --policy-name tp
(play) aws iam attach-user-policy --policy-arn arn:aws:iam::111111111111:policy/tp --user-name tu
(play) aws iam list-attached-user-policies --user-name tu
```

If we now run it without the `--dryrun` option we will ultimately see the output of the last request which was the call to `list-attached-user-policies`.

```
$ awstrace-play --trace-file create-user.trace --param user-name tu -user3 --param policy-name tp --param policy-document file://policy.json
[...]
(play) aws iam list-attached-user-policies --user-name tu
{
    "AttachedPolicies": [
        {
            "PolicyName": "tp",
            "PolicyArn": "arn:aws:iam::111111111111:policy/tp"
        }
    ]
}
[...]
```
