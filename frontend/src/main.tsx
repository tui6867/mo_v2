import { createRoot } from 'react-dom/client';
import { createClient } from '@supabase/supabase-js';
import { App } from './App';
import { api, type Config } from './api';
import './style.css';

const root = createRoot(document.getElementById('root')!);
api<Config>('/config').then(config => {
  // Auth tokens and refresh tokens remain memory-only too. A full reload may require
  // a fresh sign-in; memory-only SMTP credentials are bound to the Auth session.
  const auth = createClient(config.supabase_url, config.publishable_key, {
    auth: { persistSession: false, autoRefreshToken: true, detectSessionInUrl: true, flowType: 'implicit' },
  });
  root.render(<App config={config} auth={auth} />);
}).catch(() => root.render(<main><h1>Mail pilot unavailable</h1><p>Check the API health and development configuration. Do not enter credentials.</p></main>));
