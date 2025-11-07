# data_reader.py
import os

class DataReader:
    def __init__(self, filepath, chunk_size):
        self.chunk_size = chunk_size
        self._file = None
        self._total_chunks = 0
        try:
            file_size = os.stat(filepath)[6]
            if file_size > 0 and chunk_size > 0:
                self._total_chunks = file_size // chunk_size
            self._file = open(filepath, 'rb')
        except OSError:
            print(f"错误: 无法打开或找到数据文件 '{filepath}'")
            self._file = None
            self._total_chunks = 0

    def read_chunk(self, index):
        if not self._file or not (0 <= index < self._total_chunks):
            return None
        try:
            offset = index * self.chunk_size
            self._file.seek(offset)
            return self._file.read(self.chunk_size)
        except Exception as e:
            print(f"读取数据块 {index} 时发生错误: {e}")
            return None

    def __len__(self):
        return self._total_chunks

    def close(self):
        if self._file:
            self._file.close()
            self._file = None
            print(f"数据文件已关闭。")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()