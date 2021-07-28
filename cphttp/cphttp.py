"""

Implement a very simple reloading HTTP server for ComputePods

"""

import argparse
import asyncio
import atexit
from hypercorn.asyncio import serve
from hypercorn.config  import Config
import logging
import signal

import cphttp.fileResponsePatch

from starlette.applications import Starlette
from starlette.staticfiles  import StaticFiles

from sse_starlette.sse import EventSourceResponse
from starlette.responses import PlainTextResponse

heartBeatContinueCounting = True

def stopHeartBeat() :
  heartBeatContinueCounting = False

atexit.register(stopHeartBeat)

async def heartBeatCounter() :
  """

  A (slow) counter to act as messages over the /heartBeat SSE.

  """

  count = 0
  while heartBeatContinueCounting:
    await asyncio.sleep(2)
    yield dict(data=count)
    count = count + 1

async def heartBeatSSE(request) :
  """

  Implement the /heartBeat SSE end point.

  Start the long running counter and pass it to the sse_starlette
  EventSourceResponse.

  """
  counter = heartBeatCounter()
  return EventSourceResponse(counter)


def cphttp() :
  """

  Parse the command line arguments, configure hypercorn, setup the
  /heartBeat Server Sent Events handler using sse_starlette, and then run
  the server.

  """

  argparser = argparse.ArgumentParser(
    description="A very simple reloading Http server using SSE Starlette and Hypercorn."
  )
  argparser.add_argument("-H", "--host", default="localhost",
    help="The host interface to listen on (default: localhost)"
  )
  argparser.add_argument("-p", "--port", default=8008,
    help="The port to listen on (default: 8008)"
  )
  argparser.add_argument("-d", "--directory", default="html",
    help="The html directory to serve static files from (default: html)"
  )
  argparser.add_argument("-v", "--verbose", default=False,
    action=argparse.BooleanOptionalAction,
    help="provide more information about what is happening"
  )
  argparser.add_argument("-a", "--accesslog", default='-',
    help="specify a file for the access log (default: stdout)"
  )
  argparser.add_argument("-e", "--errorlog", default='-',
    help="specify a file for the error log (default: stdout)"
  )
  argparser.add_argument("-l", "--loglevel", default='INFO',
    help="specify the access/error logging level (default: INFO)"
  )
  cliArgs = argparser.parse_args()

  app = Starlette(debug=cliArgs.verbose)

  app.add_route(
    '/heartBeat',
    heartBeatSSE,
    name='heartBeat'
  )
  app.mount(
    '/',
    StaticFiles(directory=cliArgs.directory, html=True),
    name='home'
  )

  config = Config()
  config.bind      = [ cliArgs.host+':'+str(cliArgs.port) ]
  config.loglevel  = cliArgs.loglevel
  config.accesslog = cliArgs.accesslog
  config.errorlog  = cliArgs.errorlog
  config.log # Force the config object to instantiate the loggers

  logger = logging.getLogger('hypercorn.access')
  logger.info("Serving static files from [{}]".format(cliArgs.directory))

  shutdownHypercorn = asyncio.Event()
  def signalHandler(signum) :
    """
    Handle an OS system signal by stopping the heartBeat

    """
    print("")
    logger.info("SignalHandler: Caught signal {}".format(signum))
    stopHeartBeat()
    shutdownHypercorn.set()

  for aRoute in app.routes :
    logger.info("MountPoint: [{}]".format(aRoute.path))

  loop = asyncio.get_event_loop()
  try :
    loop.set_debug(cliArgs.verbose)
    loop.add_signal_handler(signal.SIGTERM, signalHandler, "SIGTERM")
    loop.add_signal_handler(signal.SIGHUP,  signalHandler, "SIGHUP")
    loop.add_signal_handler(signal.SIGINT,  signalHandler, "SIGINT")
    loop.run_until_complete(
      serve(app, config, shutdown_trigger=shutdownHypercorn.wait)
    )
  except Exception as err :
    msg = "\n ".join(traceback.format_exc().split("\n"))
    stopHeartBeat()
    shutdownHypercorn.set()
    logger.info("Shutting down after exception: \n {}".format(msg))
    try :
      loop.stop()
      loop.close()
    except Exception as err :
      logger.error("Could not stop asyncio loop")
      logger.error(repr(err))

  logger.info("Finised serving")
  logging.shutdown()
