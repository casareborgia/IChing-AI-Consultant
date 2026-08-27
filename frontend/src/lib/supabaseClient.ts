import { createBrowserClient } from '@supabase/ssr';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://ovkrhkfhscsyxixsxenk.supabase.co';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im92a3Joa2Zoc2NzeXhpeHN4ZW5rIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA0NTExMTcsImV4cCI6MjA5NjAyNzExN30.Y9JTdS13njPN7FRm1owfSJxtqt4ShiCDVwbMqP9yJ10';

export const supabase = createBrowserClient(supabaseUrl, supabaseAnonKey);
