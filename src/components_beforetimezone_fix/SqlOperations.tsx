import React, { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import LogDisplay from './LogDisplay';
import DatabaseConnectionSelector from './DatabaseConnectionSelector';
import { useAuth } from '@/contexts/AuthContext';

const SqlOperations = () => {
  const { toast } = useToast();
  const { user } = useAuth();
  const [selectedFT, setSelectedFT] = useState<string>('');
  const [selectedFile, setSelectedFile] = useState<string>('');
  const [selectedHostname, setSelectedHostname] = useState<string>('');
  const [selectedPort, setSelectedPort] = useState<string>('');
  const [selectedUser, setSelectedUser] = useState<string>('');
  const [dbName, setDbName] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [logs, setLogs] = useState<string[]>([]);
  const [deploymentId, setDeploymentId] = useState<string | null>(null);
  const [logStatus, setLogStatus] = useState<'idle' | 'loading' | 'running' | 'success' | 'failed'>('idle');

  // Fetch FTs
  const { data: fts = [], isLoading: isLoadingFTs } = useQuery({
    queryKey: ['fts', 'sql'],
    queryFn: async () => {
      const response = await fetch('/api/fts?type=sql');
      if (!response.ok) {
        throw new Error('Failed to fetch FTs');
      }
      return response.json();
    },
    refetchOnWindowFocus: false,
  });

  // Fetch Files for selected FT
  const { data: files = [], isLoading: isLoadingFiles } = useQuery({
    queryKey: ['ft-files', selectedFT],
    queryFn: async () => {
      if (!selectedFT) return [];
      const response = await fetch(`/api/fts/${selectedFT}/files?type=sql`);
      if (!response.ok) {
        throw new Error('Failed to fetch files');
      }
      return response.json();
    },
    enabled: !!selectedFT,
    refetchOnWindowFocus: false,
  });

  // Execute SQL mutation
  const executeSqlMutation = useMutation({
    mutationFn: async () => {

      // Get the token from localStorage
      const token = localStorage.getItem('authToken');
      
      if (!token) {
        throw new Error('No authentication token found. Please log in.');
      }
      if (!selectedFT || !selectedFile || !selectedHostname || !selectedPort || !selectedUser || !dbName) {
        throw new Error('Missing required fields');
      }

      const response = await fetch('/api/deploy/sql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ft: selectedFT,
          file: selectedFile,
          hostname: selectedHostname,
          port: selectedPort,
          dbName,
          user: selectedUser,
          password,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Failed to execute SQL');
      }

      return response.json();
    },
    onSuccess: (data) => {
      toast({
        title: "SQL Execution Started",
        description: `Deployment ID: ${data.deploymentId}`,
      });
      setDeploymentId(data.deploymentId);
      setLogStatus('running');
      pollLogs(data.deploymentId);
    },
    onError: (error) => {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : 'Failed to execute SQL',
        variant: "destructive",
      });
    },
  });

  // Poll logs when deployment starts
  const pollLogs = async (id: string) => {
    try {
      setLogStatus('loading');
      
      // Set up SSE for real-time logs
      const evtSource = new EventSource(`/api/deploy/${id}/logs`);
      
      evtSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.message) {
          setLogs(prev => [...prev, data.message]);
        }
        
        if (data.status && data.status !== 'running') {
          setLogStatus(data.status);
          evtSource.close();
        }
      };
      
      evtSource.onerror = () => {
        evtSource.close();
        // Fallback to normal polling if SSE fails
        fetchLogs(id);
      };
      
      return () => {
        evtSource.close();
      };
    } catch (error) {
      console.error('Error setting up log polling:', error);
      // Fallback to regular polling
      fetchLogs(id);
    }
  };
  
  const fetchLogs = async (id: string) => {
    try {
      const response = await fetch(`/api/deploy/${id}/logs`);
      if (!response.ok) {
        throw new Error('Failed to fetch logs');
      }
      
      const data = await response.json();
      setLogs(data.logs || []);
      
      if (data.status) {
        setLogStatus(data.status);
      }
      
      // Continue polling if still running
      if (data.status === 'running') {
        setTimeout(() => fetchLogs(id), 2000);
      }
    } catch (error) {
      console.error('Error fetching logs:', error);
      setLogStatus('failed');
    }
  };

  // Handle form submission
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setLogs([]);
    executeSqlMutation.mutate();
  };

  // Update selected file when files change or selected FT changes
  useEffect(() => {
    if (files && files.length > 0) {
      setSelectedFile(files[0]);
    } else {
      setSelectedFile('');
    }
  }, [files, selectedFT]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <Card className="bg-[#1a2b42] text-[#EEEEEE]">
        <CardHeader>
          <CardTitle>SQL Execution</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label htmlFor="ft">FT</Label>
              <Select 
                onValueChange={setSelectedFT}
                disabled={isLoadingFTs || fts.length === 0}
              >
                <SelectTrigger id="ft">
                  <SelectValue placeholder="Select FT" />
                </SelectTrigger>
                <SelectContent>
                  {fts.map((ft: string) => (
                    <SelectItem key={ft} value={ft}>{ft}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            <div>
              <Label htmlFor="file">SQL File</Label>
              <Select 
                onValueChange={setSelectedFile}
                disabled={isLoadingFiles || files.length === 0 || !selectedFT}
                value={selectedFile}
              >
                <SelectTrigger id="file">
                  <SelectValue placeholder="Select SQL File" />
                </SelectTrigger>
                <SelectContent>
                  {files.map((file: string) => (
                    <SelectItem key={file} value={file}>{file}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            <DatabaseConnectionSelector
              onConnectionChange={({hostname, port}) => {
                setSelectedHostname(hostname);
                setSelectedPort(port);
              }}
              onUserChange={setSelectedUser}
              selectedHostname={selectedHostname}
              selectedPort={selectedPort}
              selectedUser={selectedUser}
            />
            
            <div>
              <Label htmlFor="db-name">Database Name</Label>
              <Input 
                id="db-name"
                value={dbName}
                onChange={(e) => setDbName(e.target.value)}
                placeholder="Enter database name"
                required
              />
            </div>
            
            <div>
              <Label htmlFor="password">Password</Label>
              <Input 
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
              />
            </div>
            
            <Button 
              type="submit" 
              disabled={!selectedFT || !selectedFile || !selectedHostname || !selectedPort || !selectedUser || !dbName || executeSqlMutation.isPending}
              className="w-full"
            >
              {executeSqlMutation.isPending ? 'Executing...' : 'Execute SQL'}
            </Button>
          </form>
        </CardContent>
      </Card>
      
      <LogDisplay 
        logs={logs} 
        title={`SQL Execution Logs${user?.username ? ` - User: ${user.username}` : ''}`}
        height="400px"
        status={logStatus}
      />
    </div>
  );
};

export default SqlOperations;
