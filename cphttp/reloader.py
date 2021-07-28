"""

The fileResponsePatch module injects the contents of the `reloaderScript`
string, provided by this module, as a `<script>...</script>` at the end of
any HTML file's `<head>...</head>` section.

"""

reloaderScript = """

///////////////////////////////////////////////////////////////////////////
// A simple heartBeat/reload system.

// We open an EventSource (Server Sent Event stream) to the server
// ('/heartBeat') and wait for it to close (because the server is
// reloading). We then set a timer to attempt a reconnection. Once we have
// successfully reconnected we reload the page.

// We use the Page Visibility API to detect when the app is visible/hidden
// (and hence should/should-not reload)
// see: https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API

// In the future we might want to add the evolving Page Life cycle API
// see: https://wicg.github.io/page-lifecycle/
// see: https://developers.google.com/web/updates/2018/07/page-lifecycle-api#overview_of_page_lifecycle_states_and_events

var mountPoint           = '/heartBeat'
var heartBeatEventSource = null
var hasOpenedOnce        = false
var isVisible            = false
var reConnectTimer       = null
var heartBeat            = null
var logLevel             = 1

function logDebug(message) {
  if (1 < logLevel) {
    console.debug(message)
  }
}

function logInfo(message) {
  if (0 < logLevel) {
    console.info(message)
  }
}

function logError(message) {
  console.error(message)
}

window.addEventListener('visibilitychange', function () {
  isVisible = ! document.hidden
  //logDebug("MajorDomoUI visibility "+isVisible.toString())
})

// Ensure that the EventSource is closed *before* we unload this page
// (or reload it)
//
window.addEventListener("beforeunload", function(event) {
  stopReconnectTimer()
	closeHeartBeat()
})

function startReconnectTimer() {
  stopReconnectTimer()
  //logDebug("Starting reconnect timer")
  reConnectTimer = setTimeout(reConnect, 250)
}

function stopReconnectTimer() {
  if (reConnectTimer) {
    //logDebug("Stopping reconnect timer")
  	clearTimeout(reConnectTimer)
  	reConnectTimer = null
  }
}

function closeHeartBeat() {
  //logDebug("Closing heartBeat connection")
  logInfo("Stopping eventSource ["+mountPoint+"]")
  if (heartBeatEventSource) {
   	heartBeatEventSource.close()
  }
  heartBeatEventSource = null
}

function reConnect() {
  closeHeartBeat()
  logDebug("Reconnecting to heartBeat")
  logInfo("Starting eventSource ["+mountPoint+"]")
  var newEs = new EventSource(mountPoint)
  if (newEs) {
    logDebug("Adding eventSource callbacks for ["+ mountPoint +"]")
    newEs.onopen = onOpen
    newEs.onerror = onError
    newEs.addEventListener('close',   onClose)
    newEs.addEventListener('message', onMessage)
    heartBeatEventSource = newEs
  } else {
   	heartBeatEventSource = null
  }
}

function reload() {
  logDebug("Reloading window")
  /*if (isVisible)*/ window.location.reload()
}

function onOpen(evt) {
  logInfo("EventSource ["+ mountPoint +"] opened")
  stopReconnectTimer()
  //logDebug("HeartBeat connection open")
  if (hasOpenedOnce) {
    reload()
  } else {
  	hasOpenedOnce = true
  }
}

function onClose(evt) {
  logInfo("EventSource ["+ mountPoint + "] closed")
  //logDebug("HeartBeat connection closing")
  closeHeartBeat()
}

function onError(evt) {
  logError("EventSource [" + mountPoint + "] ERROR: ")
  logError(evt)
  logError("EventSource error ignored")
  //logDebug("HeartBeat connection error")
  startReconnectTimer()
}

function onMessage(evt) {
  //logDebug("EventSource ["+ mountPoint + "] MSG:")
  //logDebug(evt.data)
  //logDebug("EventSource MSG ----------------------")
  //logDebug("HeartBeat connection message")
  // ignore...
  var msg = JSON.parse(evt.data)
  logDebug("EventSource msg: ["+msg+"]")
  if (msg == 'reload') {
    reload()
  }
}

window.onload = startReconnectTimer

"""










