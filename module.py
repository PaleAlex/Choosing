from config import bucket
import re
import pandas as pd
import io
import os

def check(s):
    regex = re.compile(r"([-!#-'*+/-9=?A-Z^-~]+(\.[-!#-'*+/-9=?A-Z^-~]+)*|\"([]!#-[^-~ \t]|(\\[\t -~]))+\")@([-!#-'*+/-9=?A-Z^-~]+(\.[-!#-'*+/-9=?A-Z^-~]+)*|\[[\t -Z^-~]*])")
    if re.fullmatch(regex,s):
        return s
    else:
        return None

def read_suggests():
    data = pd.read_csv(
                    io.BytesIO(
                        bucket.blob(blob_name = "suggests.csv").download_as_bytes()
                    ),
                    index_col = 0, encoding = 'utf-8'
                )
    return data

def read_final():
    data = pd.read_csv(
                        io.BytesIO(
                            bucket.blob(blob_name = "final.csv").download_as_bytes()
                        ),
                        index_col = 0, encoding = 'utf-8'
                    )
    return data

def read_usertemp(username):
    data = pd.read_csv(
                io.BytesIO(
                    bucket.blob(blob_name = f"user_temps/temp_{username}.csv").download_as_bytes()
                ),
                index_col = 0, encoding = 'utf-8'
            )
    return data

def upload(filename):
    UPLOADFILE = os.path.join(os.getcwd(),filename)
    blob = bucket.blob(filename)
    blob.upload_from_filename(UPLOADFILE)
    return True