from dataclasses import dataclass
from typing import Generator, Union

from src.hugchat.exceptions import ChatError, ModelOverloadedError


MSGTYPE_FINAL = "finalAnswer"
MSGTYPE_STREAM = "stream"
MSGTYPE_WEB = "webSearch"
MSGTYPE_STATUS = "status"

MSGSTATUS_PENDING = 0
MSGSTATUS_RESOLVED = 1
MSGSTATUS_REJECTED = 2


class WebSearchSource:
    title: str
    link: str
    hostname: str


@dataclass
class Message(Generator):
    """
    :Args:
        * g: Generator
        * _stream_yield_all: bool = False
        * web_search: bool = False
        - web_search_sources: list[WebSearchSource] = list()
        - final_answer: str = ""
        - web_search_done: bool = not web_search
        - msg_status: int = MSGSTATUS_PENDING
        - error: Union[Exception, None] = None

    A wrapper of `Generator` that receives and process the response

    :Example:
    .. code-block:: python
        
        msg = bot.chat(...)

        # stream process
        for res in msg:
            ... # process
        else:
            if msg.done() == MSGSTATUS_REJECTED:
                raise msg.error

        # or simply use:
        final = msg.wait_until_done()
    """
    g: Generator
    _stream_yield_all: bool = False
    web_search: bool = False
    web_search_sources: list[WebSearchSource] = list()
    final_answer: str = ""
    web_search_done: bool = not web_search
    msg_status: int = MSGSTATUS_PENDING
    error: Union[Exception, None] = None

    def __next__(self):
        if self.msg_status:
            raise StopIteration

        try:
            a: dict = next(self.g)
            t: str = a["type"]
            if t == MSGTYPE_STREAM:
                self.web_search_done = True
            elif t == MSGTYPE_STATUS:
                pass
            elif t == MSGTYPE_FINAL:
                self.final_answer = a["text"]
                self.msg_status = MSGSTATUS_RESOLVED
            elif t == MSGTYPE_WEB:
                if a.__contains__("sources"):
                    self.web_search_sources = list()
                    sources = a["sources"]
                    for source in sources:
                        wss = WebSearchSource()
                        wss.title = source["title"]
                        wss.link = source["link"]
                        wss.hostname = source["hostname"]
                        self.web_search_sources.append(wss)
            else:
                if "Model is overloaded" in str(a):
                    self.error = ModelOverloadedError(
                        "Model is overloaded, please try again later or switch to another model."
                    )
                    self.msg_status = MSGSTATUS_REJECTED
                elif a.__contains__("error"):
                    self.error = ChatError(a["error"])
                    self.msg_status = MSGSTATUS_REJECTED
                else:
                    self.error = ChatError(f"Unknow json response: {a}")

            # If _stream_yield_all is True, yield all responses from the server.
            if self._stream_yield_all or t == MSGTYPE_STREAM:
                return a
        except Exception as e:
            self.error = e
            self.msg_status = MSGSTATUS_REJECTED

    def __iter__(self):
        return self

    def throw(
        self,
        __typ: type[BaseException],
        __val: Union[BaseException, object] = None,
        __tb=None,
    ):
        return self.g.throw(__typ, __val, __tb)

    def send(self, __value):
        return self.g.send(__value)

    def wait_until_done(self) -> str:
        """
        :Return:
            - self.final_answer if resolved else raise error

        wait until every response is resolved
        """
        while not self.done():
            self.__next__()
        if self.done() == MSGSTATUS_RESOLVED:
            return self.final_answer
        elif self.error != None:
            raise self.error
        else:
            raise Exception("Rejected but no error captured!")

    def done(self):
        """
        :Return:
            - self.msg_status

        3 status:
        - MSGSTATUS_PENDING = 0    # running
        - MSGSTATUS_RESOLVED = 1   # done with no error(maybe?)
        - MSGSTATUS_REJECTED = 2   # error raised
        """
        return self.msg_status

    def done_search(self):
        """
        :Return:
            - self.web_search_done

        web search result will be set to `done` once the token is received
        """
        return self.web_search_done


if __name__ == "__main__":
    pass
