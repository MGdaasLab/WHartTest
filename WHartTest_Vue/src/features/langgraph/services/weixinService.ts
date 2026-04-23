import { request } from '@/utils/request';

export interface WeixinLoginSession {
  session_key: string;
  status: 'wait' | 'scaned' | 'confirmed' | 'expired' | 'failed';
  qr_data_url: string;
  raw_account_id: string;
  account_id: string;
  scanned_user_id: string;
  error_message: string;
  expires_at: string;
  created_at: string;
  updated_at: string;
}

export interface WeixinBotAccount {
  id: number;
  raw_account_id: string;
  account_id: string;
  project: number;
  project_name: string;
  prompt: number | null;
  prompt_name?: string;
  scanned_user_id: string;
  is_active: boolean;
  worker_running: boolean;
  status: string;
  last_error: string;
  last_inbound_at?: string | null;
  last_outbound_at?: string | null;
  created_at: string;
  updated_at: string;
}

export async function startWeixinLogin(data: {
  project_id: number;
  prompt_id?: number | null;
}) {
  return request<WeixinLoginSession>({
    url: '/weixin/login/start/',
    method: 'POST',
    data,
  });
}

export async function getWeixinLoginStatus(sessionKey: string) {
  return request<WeixinLoginSession>({
    url: `/weixin/login/${sessionKey}/status/`,
    method: 'GET',
  });
}

export async function getWeixinAccounts(projectId?: number | null) {
  return request<WeixinBotAccount[]>({
    url: '/weixin/accounts/',
    method: 'GET',
    params: projectId ? { project_id: projectId } : undefined,
  });
}

export async function toggleWeixinAccount(accountId: number, isActive: boolean) {
  return request<WeixinBotAccount>({
    url: `/weixin/accounts/${accountId}/toggle/`,
    method: 'POST',
    data: { is_active: isActive },
  });
}
