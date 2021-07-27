"""

This fileResponsePatch module monkey patches the
`Starlette::FileResponse.__call__` to allow us to inject our
`reloaderScript` JavaScript into any HTML responses.

"""

# We model our code (below) on the corresponding code in the
# Starlette::FileResponse.__call__ taken on 27 July 2021 from the pdm
# installed version of Starlette v0.16.0 from pypi. This code is used
# under a BSD 3-clause "New" or "Revised" License:

# Copyright © 2018, Encode OSS Ltd. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
# - Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
#
# - Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
#
# - Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
# IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED
# TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import anyio
import logging
logger = logging.getLogger('hypercorn.access')

from starlette.responses import FileResponse
from starlette.types import Receive, Scope, Send

from .reloader import reloaderScript

oldFileResponseCall = FileResponse.__call__

async def newFileResponseCall(self, scope: Scope, receive: Receive, send: Send) -> None:
  """

  A monkey patched version of the `Starlette::FileResponse.__call__` method.

  This version detects if the media_type is HTML and if so, reads the file
  line by line looking for the `</head>` element. When found the `</head>`
  string is replaced by a `<script>...</script></head>` string which
  contains the `reloaderScript` from the `cphttp.reloader`

  If the file is *not* an HTML file, the original
  `Starlette::FileResponse.__call__` is called.

  This code is based on the original `Starlette::FileResponse.__call__`
  code. It is used under Starlette's BSD License (see the top of the
  fileResonsePatch.py file for details)

  """

  if not self.media_type.endswith("html") :
    return await oldFileResponseCall(self, scope, receive, send)

  logger.debug("Injecting reloader into [{}]".format(self.path))

  headReplacementStr = """
    <script>{}</script>
  </head>
""".format(reloaderScript)
  headReplacementSize = len(headReplacementStr) - len('</head>')

  if self.stat_result is None:
    try:
      stat_result = await anyio.to_thread.run_sync(os.stat, self.path)
      self.set_stat_headers(stat_result)
    except FileNotFoundError:
      raise RuntimeError(f"File at path {self.path} does not exist.")
    else:
      mode = stat_result.st_mode
      if not stat.S_ISREG(mode):
        raise RuntimeError(f"File at path {self.path} is not a file.")
  self.headers['content-length'] = str(self.stat_result.st_size + headReplacementSize)
  await send(
    {
      "type": "http.response.start",
      "status": self.status_code,
      "headers": self.raw_headers,
    }
  )
  if self.send_header_only:
    await send({"type": "http.response.body", "body": b"", "more_body": False})
  else:
    async with await anyio.open_file(self.path, mode="r") as file:
      more_body = True
      while more_body:
        aLine = await file.readline()
        more_body = len(aLine) != 0
        if -1 < aLine.find('</head>') :
          aLine = aLine.replace('</head>', headReplacementStr)
        await send(
          {
            "type": "http.response.body",
            "body": bytes(aLine, 'utf-8'),
            "more_body": more_body,
          }
        )
  if self.background is not None:
    await self.background()

FileResponse.__call__ = newFileResponseCall

