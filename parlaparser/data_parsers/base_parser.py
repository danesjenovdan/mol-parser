import pdftotext
import requests
from docx import Document


class BaseParser(object):
    def __init__(self, data_storage):
        self.data_storage = data_storage
        pass


class PdfParser(BaseParser):
    def __init__(self, data_storage, url, file_name):
        super().__init__(data_storage)
        response = requests.get(url)
        with open(f"parlaparser/files/{file_name}", "wb") as f:
            f.write(response.content)

        with open(f"parlaparser/files/{file_name}", "rb") as f:
            self.pdf = pdftotext.PDF(f, physical=True)


class DocxParser(BaseParser):
    def __init__(self, data_storage, url, file_name):
        super().__init__(data_storage)
        response = requests.get(url)
        with open(f"parlaparser/files/{file_name}", "wb") as f:
            f.write(response.content)

        f = open(f"parlaparser/files/{file_name}", "rb")
        self.document = Document(f)
        f.close()
