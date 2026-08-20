import { Message } from '@arco-design/web-vue';

export interface ApiExtractPersistenceResult {
  matched_count: number;
  created_count: number;
  updated_count: number;
  skipped_no_environment: boolean;
}

export const showExtractPersistenceNotice = (
  extractPersistence?: ApiExtractPersistenceResult | null,
) => {
  if (!extractPersistence?.skipped_no_environment) {
    return;
  }

  if ((extractPersistence.matched_count ?? 0) <= 0) {
    return;
  }

  Message.warning('检测到项目变量提取，但当前未选择环境，本次已跳过保存到项目变量');
};
