/**
 * Copyright 2019 The Gamma Authors.
 *
 * This source code is licensed under the Apache License, Version 2.0 license
 * found in the LICENSE file in the root directory of this source tree.
 */

#pragma once

#include <string>

#include "async_flush.h"
#include "raw_vector_io.h"
#include "vector/memory_raw_vector.h"
#include "vector/rocksdb_wrapper.h"

namespace vearch {

struct MemoryRawVectorIO : public RawVectorIO, public AsyncFlusher {
  MemoryRawVector *raw_vector;
  RocksDBWrapper rdb;

  MemoryRawVectorIO(MemoryRawVector *raw_vector_)
      : AsyncFlusher(raw_vector_->MetaInfo()->Name()),
        raw_vector(raw_vector_) {}
  ~MemoryRawVectorIO() {}
  Status Init() override;
  Status Dump(int start_vid, int end_vid) override;
  int GetDiskVecNum(int &vec_num) override;
  Status Load(int vec_num) override;
  Status Update(int vid) override;

  Status FlushOnce() override;

  Status Put(int vid);
};

}  // namespace vearch
