import type { UserBrief } from './common';

export type DatabaseType = 'mysql' | 'postgresql' | 'sqlite' | 'oracle' | 'sqlserver';

export interface ApiDatabaseConfig {
  id: number;
  name: string;
  project: number;
  db_type: DatabaseType;
  host: string;
  port: number;
  username: string;
  password: string;
  database: string;
  charset: string;
  is_active: boolean;
  description: string;
  psm: string;
  verify_ssl: boolean;
  connection_params: Record<string, any>;
  created_by: UserBrief | null;
  created_at: string;
  updated_at: string;
  [key: string]: any;
}
