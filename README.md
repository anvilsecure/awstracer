# AWS CLI Tracer

![Example Terminal Session](/termsession_example.svg?raw=true&sanitize=true)

## Example: Creating a DynamoDB table and filling it with data

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
[..]
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
[..]
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


## Usage

## Installation

Please note that this tool requires at least Python `>= 3.6`.  To install from pip just run `python3 -m pip install awstracer`. To install from source simply clone the repository and run:

```
$ python setup.py sdist
$ pip install dist/awstracer-1.0.tar.gz
```
