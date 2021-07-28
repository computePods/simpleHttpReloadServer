# ComputePods Simple reloading HTTP server

A very simple reloading HTTP server using SSE Starlette and Hypercorn.

## Usage:

```
usage: cphttp [-h] [-H HOST] [-p PORT] [-d DIRECTORY]
              [-v | --verbose | --no-verbose] [-a ACCESSLOG] [-e ERRORLOG]
              [-l LOGLEVEL]

A very simple reloading Http server using SSE Starlette and Hypercorn.

optional arguments:
  -h, --help            show this help message and exit
  -H HOST, --host HOST  The host interface to listen on (default: localhost)
  -p PORT, --port PORT  The port to listen on (default: 8008)
  -d DIRECTORY, --directory DIRECTORY
                        The html directory to serve static files from (default:
                        html)
  -v, --verbose, --no-verbose
                        provide more information about what is happening
                        (default: False)
  -a ACCESSLOG, --accesslog ACCESSLOG
                        specify a file for the access log (default: stdout)
  -e ERRORLOG, --errorlog ERRORLOG
                        specify a file for the error log (default: stdout)
  -l LOGLEVEL, --loglevel LOGLEVEL
                        specify the access/error logging level (default: INFO)
  -w WATCH, --watch WATCH
                        sepcify the directories/files to watch (can be used
                        multiple times) (default: none)
```
