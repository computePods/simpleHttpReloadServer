""" Implement a very simple reloading HTTP server for ComputePods """

import argparse
# These two imports on adjacent lines confuse the spell checker ;-(
import asyncio
import atexit
from hypercorn.asyncio import serve
from hypercorn.config  import Config

import json
import logging
import signal

import cphttp.fileResponsePatch
from .fsWatcher import FSWatcher

from starlette.applications import Starlette
from starlette.staticfiles  import StaticFiles

from sse_starlette.sse import EventSourceResponse
from starlette.responses import PlainTextResponse

#########################################################################
# manage the HeartBeat SSE

heartBeatQueue = asyncio.Queue()

heartBeatContinueBeating = True
def stopHeartBeat() :
  heartBeatContinueBeating = False
atexit.register(stopHeartBeat)

async def heartBeatCounter() :
  """ A (slow) counter to act as messages over the /heartBeat SSE which
  help keep the connection open when run through an HTTP-proxy. """

  count = 0
  while heartBeatContinueBeating:
    await asyncio.sleep(2)
    await heartBeatQueue.put(str(count))
    count = count + 1

async def heartBeatBeater() :
  """ The SSE generator of messages to be sent over the /heartBeat SSE.

  Using an asyncio.Queue allows the counter and reload messages to be
  interleaved. """

  while heartBeatContinueBeating:
    theMessage = await heartBeatQueue.get()
    yield dict(data=json.dumps(theMessage))
    heartBeatQueue.task_done()

async def heartBeatSSE(request) :
  """ Implement the /heartBeat SSE end point.

  Start the long running counter and pass it to the sse_starlette
  EventSourceResponse. """

  asyncio.create_task(heartBeatCounter())

  beater = heartBeatBeater()
  return EventSourceResponse(beater)

#########################################################################
# Manage detecting when to reload

class DebouncingTimer:
  """ A simple debouncing timer which ensures we wait until any high
  frequency events have stopped. """

  def __init__(self, timeout):
    self.timeout    = timeout
    self.taskFuture = None

  def cancelTask(self) :
    """Cancel the current timer."""

    if self.taskFuture :
      self.taskFuture.cancel()

  async def doTask(self) :
    """Sleep for timeout seconds while waiting to be (potentially)
    cancelled. If we are not cancelled, send a `reload` message to the
    browser."""

    await asyncio.sleep(self.timeout)
    await heartBeatQueue.put("reload")

  async def reStart(self) :
    """Restart the timer (cancel the old one if it exists)."""

    self.cancelTask()
    self.taskFuture = asyncio.ensure_future(self.doTask())

async def watchFiles(cliArgs, logger) :
  """Setup the file system watcher."""

  aWatcher = FSWatcher(logger)
  aTimer   = DebouncingTimer(1)

  asyncio.create_task(aWatcher.managePathsToWatchQueue())

  for aWatch in cliArgs.watch :
    await aWatcher.watchARootPath(aWatch)

  async for event in aWatcher.watchForFileSystemEvents() :
    await aTimer.reStart()

#########################################################################
# setup the webserver

shutdownHypercorn = asyncio.Event()
def stopWebServer() :
  """Tell the Hypercorn server to stop."""

  shutdownHypercorn.set()
atexit.register(stopWebServer)

def configureWebServer(cliArgs) :
  """ Configure the Hypercorn webserver."""

  config = Config()
  config.bind      = [ cliArgs.host+':'+str(cliArgs.port) ]
  config.loglevel  = cliArgs.loglevel
  config.accesslog = cliArgs.accesslog
  config.errorlog  = cliArgs.errorlog
  config.log # Force the config object to instantiate the loggers

  return (
    logging.getLogger('hypercorn.access'),
    config
  )

async def runWebServer(cliArgs, logger, config) :
  """Setup the Starlette Application and run it."""

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

  logger.info("Serving static files from [{}]".format(cliArgs.directory))

  for aRoute in app.routes :
    logger.info("MountPoint: [{}]".format(aRoute.path))

  await serve(app, config, shutdown_trigger=shutdownHypercorn.wait)

#########################################################################
# Main command line

def signalHandler(signum, logger) :
  """ Handle an OS system signal by stopping the heartBeat """

  print("")
  logger.info("SignalHandler: Caught signal {}".format(signum))
  stopHeartBeat()
  shutdownHypercorn.set()

async def runUntilShutdown(cliArgs, logger, config) :
  asyncio.create_task(watchFiles(cliArgs, logger))
  asyncio.create_task(runWebServer(cliArgs, logger, config))
  await shutdownHypercorn.wait()

def cphttp() :
  """ Parse the command line arguments, configure hypercorn, setup the
  /heartBeat Server Sent Events handler using sse_starlette, and then run
  the server. """

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
  argparser.add_argument("-w", "--watch", default=[], action='append',
    help="sepcify the directories/files to watch (can be used multiple times) (default: none)"
  )
  cliArgs = argparser.parse_args()
  logger, config = configureWebServer(cliArgs)

  # setup the asyncio loop

  loop = asyncio.get_event_loop()
  loop.set_debug(cliArgs.verbose)
  loop.add_signal_handler(signal.SIGTERM, signalHandler, "SIGTERM", logger)
  loop.add_signal_handler(signal.SIGHUP,  signalHandler, "SIGHUP",  logger)
  loop.add_signal_handler(signal.SIGINT,  signalHandler, "SIGINT",  logger)
  loop.run_until_complete(runUntilShutdown(cliArgs, logger, config))

  logger.info("Finised serving")
  logging.shutdown()
