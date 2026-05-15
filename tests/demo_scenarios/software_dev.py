"""
Demo scenario 4: Software Development
Plant a hallucinated npm package name (slopsquatting risk).
"""

HALLUCINATED_OUTPUT = """
Here's how to implement data fetching with caching in your React application:

First, install the required packages:
npm install react-query-optimizer axios-cache-interceptor

Then use it in your component:

import { useOptimizedQuery } from 'react-query-optimizer';
import { setupCache } from 'axios-cache-interceptor';

const { data, isLoading, error } = useOptimizedQuery({
  queryKey: ['users'],
  queryFn: () => fetch('/api/users').then(r => r.json()),
  staleTime: 5 * 60 * 1000,
  cacheTime: 10 * 60 * 1000,
});

This will automatically handle caching and background refetching.
The react-query-optimizer package is battle-tested and used by thousands of companies.
"""
