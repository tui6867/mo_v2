import { createRoot } from 'react-dom/client';
import { createClient } from '@supabase/supabase-js';
import '@fontsource-variable/manrope';
import { App } from './App';
import { api } from './api';
import './styles.css';
const root = createRoot(document.getElementById('root')!);
api<{ supabase_url: string; publishable_key: string; live_transport_available: boolean }>('/config').then(config => {
  const auth = createClient(config.supabase_url, config.publishable_key, { auth: { persistSession: false, autoRefreshToken: true, detectSessionInUrl: true, flowType: 'implicit' } });
  root.render(<App auth={auth} transportAvailable={config.live_transport_available} />);
}).catch(() => root.render(<main className="auth-shell"><h1>Workspace unavailable</h1><p>Deployment configuration is incomplete. Contact the administrator. Do not enter Gmail credentials.</p></main>));
