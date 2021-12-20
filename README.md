# mol-parser

## parse people
scrapy crawl people

## parse sessions with speeches and votes
scrapy crawl sessions -a parse_type=votes/speeches/question -a parse_name="session name"
