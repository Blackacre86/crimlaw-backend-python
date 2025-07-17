const API_BASE_URL = 'https://crimlaw-backend-python-production.up.railway.app';
// src/utils/api.ts – Helper to talk to the backend
import { createClient } from '@supabase/supabase-js'; // For login safety

const API_BASE_URL = 'https://crimlaw-backend-python-production.up.railway.app'; // Backend address
const supabase = createClient(import.meta.env.VITE_SUPABASE_URL, import.meta.env.VITE_SUPABASE_ANON_KEY); // Login setup (already in your code)

// Get a safe key for talking
const getAuthHeaders = async () => {
  const { data: { session } } = await supabase.auth.getSession();
  return {
    Authorization: `Bearer ${session?.access_token ?? ''}`, // Login key
    'Content-Type': 'application/json', // Type of message
  };
};

// Send a question, like a search
export const apiPost = async <T>(endpoint: string, body: unknown): Promise<T> => {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: 'POST', // Sending something new
    headers,
    body: JSON.stringify(body), // Turn question into code
  });
  if (!response.ok) throw new Error(`Oops: ${response.statusText}`); // If problem
  return response.json(); // Get answer
};

// Get info, like checking status
export const apiGet = async <T>(endpoint: string): Promise<T> => {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}${endpoint}`, { method: 'GET', headers });
  if (!response.ok) throw new Error(`Oops: ${response.statusText}`);
  return response.json();
};

// Example: Use in your app screens with React Query to remember answers and make it fast on phones.