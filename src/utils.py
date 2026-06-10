from __future__ import annotations

import io
import os
from typing import Optional

import pandas as pd


def read_tabular_file(file_bytes: bytes, filename: str) -> pd.DataFrame:
    name = filename.lower()
    bio = io.BytesIO(file_bytes)
    if name.endswith(".csv"):
        return pd.read_csv(bio)
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(bio)
    raise ValueError("Unsupported file type. Please upload CSV or Excel.")


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def dataframe_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Results") -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    bio.seek(0)
    return bio.read()