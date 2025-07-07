import React, { useState, useEffect, useCallback } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { useQuery, useMutation } from '@tanstack/react-query';
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from "@/components/ui/select";
import { RefreshCcw } from 'lucide-react';
import LogDisplay from '@/components/LogDisplay';
import VMSelector from '@/components/VMSelector';
import { useAuth } from '@/contexts/AuthContext';

const FileOperations: React.FC = () => {
  const { toast } = useToast();
  const [selectedFt, setSelectedFt] = useState<string>("");
  const [selectedFile, setSelectedFile] = useState<string>("");
  const [selectedUser, setSelectedUser] = useState<string>("infadm");
  const [targetPath, setTargetPath] = useState<string>("");
  const [selectedVMs, setSelectedVMs] = useState<string[]>([]);
  const [useSudo, setUseSudo] = useState<boolean>(false);
  const [createBackup, setCreateBackup] = useState<boolean>(true);
  const [fileLogs, setFileLogs] = useState<string[]>([]);
  const [deploymentId, setDeploymentId] = useState<string | null>(null);
  const [validateUseSudo, setValidateUseSudo] = useState<boolean>(false);
  const [fileOperationStatus, setFileOperationStatus] = useState<'idle' | 'loading' | 'running' | 'success' | 'failed' | 'completed'>('idle');
  const { user } = useAuth();
  // Shell command options
  const [shellCommand, setShellCommand] = useState<string>("");
  const [shellSelectedVMs, setShellSelectedVMs] = useState<string[]>([]);
  const [shellSelectedUser, setShellSelectedUser] = useState<string>("infadm");
  const [shellUseSudo, setShellUseSudo] = useState<boolean>(false);
  const [useUserHomePath, setUseUserHomePath] = useState<boolean>(true);
  const [shellWorkingDir, setShellWorkingDir] = useState<string>("");
  const [shellCommandId, setShellCommandId] = useState<string | null>(null);
  const [shellLogs, setShellLogs] = useState<string[]>([]);
  const [shellOperationStatus, setShellOperationStatus] = useState<'idle' | 'loading' | 'running' | 'success' | 'failed' | 'completed'>('idle');
  const [userHomes] = useState<{[key: string]: string}>({
    'infadm': '/home/users/infadm',
    'abpwrk1': '/home/users/abpwrk1',
    'root': '/root'
  });

  // Enhanced rollback state management
  const [selectedRollbackId, setSelectedRollbackId] = useState<string | null>(null);
  const [selectedDeploymentDetails, setSelectedDeploymentDetails] = useState<any | null>(null);
  
  // Auto-refresh functionality
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState<boolean>(false);
  const [refreshInterval, setRefreshInterval] = useState<number>(30000); // 30 seconds default
  const [lastRefreshTime, setLastRefreshTime] = useState<Date | null>(null);
  const [manualRefreshLoading, setManualRefreshLoading] = useState<boolean>(false);

  // Fetch all FTs
  const { data: fts = [] } = useQuery({
    queryKey: ['fts'],
    queryFn: async () => {
      const response = await fetch('/api/fts');
      if (!response.ok) {
        throw new Error('Failed to fetch FTs');
      }
      return response.json();
    },
    refetchOnWindowFocus: false,
  });

  // Fetch files for selected FT
  const { data: files = [] } = useQuery({
    queryKey: ['files', selectedFt],
    queryFn: async () => {
      if (!selectedFt) return [];
      const response = await fetch(`/api/fts/${selectedFt}/files`);
      if (!response.ok) {
        throw new Error('Failed to fetch files');
      }
      return response.json();
    },
    enabled: !!selectedFt,
    refetchOnWindowFocus: false,
  });

  // Enhanced recent file deployments query with auto-refresh
  const {
    data: recentFileDeployments = [],
    refetch: refetchRecentFileDeployments,
    isLoading: isLoadingDeployments,
    isError: isDeploymentsError,
    error: deploymentsError
  } = useQuery({
    queryKey: ['recent-file-deployments'],
    queryFn: async () => {
      try {
        const response = await fetch('/api/deployments/files/recent');
        if (!response.ok) {
          const errorText = await response.text();
          console.error(`Failed to fetch recent deployments: ${errorText}`);
          throw new Error(`HTTP ${response.status}: ${errorText}`);
        }
        const data = await response.json();
        const filteredData = data
          .filter((deployment: any) => 
            deployment.type === 'file' && deployment.status === 'success'
          )
          .slice(0, 15); // Get last 15 successful file deployments
        
        setLastRefreshTime(new Date());
        return filteredData;
      } catch (error) {
        console.error('Error fetching recent deployments:', error);
        throw error;
      }
    },
    refetchOnWindowFocus: false,
    staleTime: 10000, // 10 seconds
    refetchInterval: autoRefreshEnabled ? refreshInterval : false,
  });

  // Manual refresh function
  const handleManualRefresh = useCallback(async () => {
    setManualRefreshLoading(true);
    try {
      await refetchRecentFileDeployments();
      toast({
        title: "Refresh Complete",
        description: "Deployment list has been updated.",
      });
    } catch (error) {
      toast({
        title: "Refresh Failed",
        description: error instanceof Error ? error.message : "Failed to refresh deployment list",
        variant: "destructive",
      });
    } finally {
      setManualRefreshLoading(false);
    }
  }, [refetchRecentFileDeployments, toast]);

  // Handle rollback selection change
  const handleRollbackSelection = useCallback((deploymentId: string) => {
    setSelectedRollbackId(deploymentId);
    const selectedDeployment = recentFileDeployments.find((d: any) => d.id === deploymentId);
    setSelectedDeploymentDetails(selectedDeployment || null);
  }, [recentFileDeployments]);

  // Deploy mutation

  const deployMutation = useMutation({
  mutationFn: async () => {
    setFileOperationStatus('loading');
    
    // Get the token from localStorage
    const token = localStorage.getItem('authToken');
    
    if (!token) {
      throw new Error('No authentication token found. Please log in.');
    }
    
    const response = await fetch('/api/deploy/file', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        ft: selectedFt,
        file: selectedFile,
        user: selectedUser,
        targetPath,
        vms: selectedVMs,
        sudo: useSudo,
        createBackup: createBackup,
      }),
    });
  // const deployMutation = useMutation({
  //   mutationFn: async () => {
  //     setFileOperationStatus('loading');
  //     const response = await fetch('/api/deploy/file', {
  //       method: 'POST',
  //       headers: {
  //         'Content-Type': 'application/json',
  //       },
  //       body: JSON.stringify({
  //         ft: selectedFt,
  //         file: selectedFile,
  //         user: selectedUser,
  //         targetPath,
  //         vms: selectedVMs,
  //         sudo: useSudo,
  //         createBackup: createBackup,
  //       }),
  //     });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Failed to deploy');
      }
      
      const data = await response.json();
      setDeploymentId(data.deploymentId);
      setFileOperationStatus('running');
      return data;
    },
    onSuccess: (data) => {
      toast({
        title: "Deployment Started",
        description: "File deployment has been initiated.",
      });
      
      // Start polling for logs and refresh deployment list
      pollLogs(data.deploymentId, setFileLogs, setFileOperationStatus);
      
      // Refresh deployment list to include new deployment
      setTimeout(() => {
        refetchRecentFileDeployments();
      }, 2000);
    },
    onError: (error) => {
      setFileOperationStatus('failed');
      toast({
        title: "Deployment Failed",
        description: error instanceof Error ? error.message : "An unknown error occurred",
        variant: "destructive",
      });
    },
  });

  // Enhanced rollback mutation
  const rollbackMutation = useMutation({
    mutationFn: async (deploymentId: string) => {
      setFileOperationStatus('loading');
      // Get the token from localStorage
      const token = localStorage.getItem('authToken');
      
      if (!token) {
        throw new Error('No authentication token found. Please log in.');
      }

      const response = await fetch(`/api/deploy/${deploymentId}/rollback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        }
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Failed to rollback deployment');
      }
      
      const data = await response.json();
      setDeploymentId(data.deploymentId);
      setFileOperationStatus('running');
      return data;
    },
    onSuccess: (data) => {
      toast({
        title: "Rollback Started",
        description: "File rollback has been initiated successfully.",
      });
      
      // Start polling for logs
      pollLogs(data.deploymentId, setFileLogs, setFileOperationStatus);
      
      // Clear rollback selection and refresh list
      setSelectedRollbackId(null);
      setSelectedDeploymentDetails(null);
      
      // Refresh deployment list
      setTimeout(() => {
        refetchRecentFileDeployments();
      }, 2000);
    },
    onError: (error) => {
      setFileOperationStatus('failed');
      toast({
        title: "Rollback Failed",
        description: error instanceof Error ? error.message : "An unknown error occurred during rollback",
        variant: "destructive",
      });
    },
  });

  // Validate mutation
  const validateMutation = useMutation({
    mutationFn: async () => {
      if (!deploymentId) {
        throw new Error('No active deployment to validate');
      }
      
      const response = await fetch(`/api/deploy/${deploymentId}/validate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          sudo: validateUseSudo
        })
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Validation failed');
      }
      
      return response.json();
    },
    onSuccess: (data) => {
      toast({
        title: "Validation Complete",
        description: "File checksum validation has been completed.",
      });
      if (data.results) {
        data.results.forEach((result: any) => {
          const checksum = result.cksum ? `Checksum=${result.cksum}` : 'No checksum available';
          const permissions = result.permissions ? `Permissions: ${result.permissions}` : '';
          
          setFileLogs(prev => [
            ...prev, 
            `Validation on ${result.vm}: ${result.status}`, 
            checksum, 
            permissions
          ]);
        });
      }
    },
    onError: (error) => {
      toast({
        title: "Validation Failed",
        description: error instanceof Error ? error.message : "An unknown error occurred during validation",
        variant: "destructive",
      });
    },
  });

  // Run shell command mutation
  const shellCommandMutation = useMutation({
    mutationFn: async () => {
      setShellOperationStatus('loading');
      // Get the token from localStorage
      const token = localStorage.getItem('authToken');
      
      if (!token) {
        throw new Error('No authentication token found. Please log in.');
      }
      
      let workingDirectory = shellWorkingDir;
      
      if (useUserHomePath && !shellWorkingDir) {
        workingDirectory = userHomes[shellSelectedUser] || `/home/${shellSelectedUser}`;
      }
      
      const response = await fetch('/api/command/shell', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          command: shellCommand,
          vms: shellSelectedVMs,
          sudo: shellUseSudo,
          user: shellSelectedUser,
          workingDir: workingDirectory,
        }),
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Shell command execution failed');
      }
      
      const data = await response.json();
      setShellCommandId(data.deploymentId || data.commandId);
      setShellOperationStatus('running');
      return data;
    },
    onSuccess: (data) => {
      toast({
        title: "Command Executed",
        description: "Shell command has been initiated.",
      });
      
      pollLogs(data.deploymentId || data.commandId, setShellLogs, setShellOperationStatus);
    },
    onError: (error) => {
      setShellOperationStatus('failed');
      toast({
        title: "Command Failed",
        description: error instanceof Error ? error.message : "An unknown error occurred",
        variant: "destructive",
      });
    },
  });

  // Generic function to poll for logs with improved completion detection
  const pollLogs = (id: string, logSetter: React.Dispatch<React.SetStateAction<string[]>>, statusSetter: React.Dispatch<React.SetStateAction<'idle' | 'loading' | 'running' | 'success' | 'failed' | 'completed'>>) => {
    if (!id) return;
    
    logSetter([]);
    statusSetter('running');
    
    let pollCount = 0;
    let lastLogLength = 0;
    
    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`/api/deploy/${id}/logs`);
        if (!response.ok) {
          throw new Error('Failed to fetch logs');
        }
        
        const data = await response.json();
        if (data.logs) {
          logSetter(data.logs);
          
          if (data.status === 'completed' || data.status === 'success') {
            statusSetter('success');
            clearInterval(pollInterval);
            return;
          }
          
          if (data.status === 'failed') {
            statusSetter('failed');
            clearInterval(pollInterval);
            return;
          }
          
          if (data.logs.length === lastLogLength) {
            pollCount++;
            if (pollCount >= 5) {
              console.log('Operation appears complete - logs have not changed');
              statusSetter('success');
              clearInterval(pollInterval);
              return;
            }
          } else {
            pollCount = 0;
            lastLogLength = data.logs.length;
          }
        }
        
        if (pollCount > 120) {
          console.log('Operation timed out after 2 minutes');
          statusSetter(data.status === 'running' ? 'running' : 'completed');
          clearInterval(pollInterval);
        }
      } catch (error) {
        console.error('Error fetching logs:', error);
        pollCount += 5;
        if (pollCount > 20) {
          statusSetter('failed');
          clearInterval(pollInterval);
        }
      }
    }, 1000);
    
    return () => {
      clearInterval(pollInterval);
    };
  };

  const handleVMSelectionChange = (vms: string[]) => {
    setSelectedVMs(vms);
  };
  
  const handleShellVMSelectionChange = (vms: string[]) => {
    setShellSelectedVMs(vms);
  };

  const handleDeploy = (e: React.MouseEvent) => {
    e.preventDefault();
    
    if (!selectedFt) {
      toast({
        title: "Validation Error",
        description: "Please select an FT.",
        variant: "destructive",
      });
      return;
    }
    
    if (!selectedFile) {
      toast({
        title: "Validation Error",
        description: "Please select a file.",
        variant: "destructive",
      });
      return;
    }
    
    if (!targetPath) {
      toast({
        title: "Validation Error",
        description: "Please enter a target path.",
        variant: "destructive",
      });
      return;
    }
    
    if (selectedVMs.length === 0) {
      toast({
        title: "Validation Error",
        description: "Please select at least one VM.",
        variant: "destructive",
      });
      return;
    }

    setFileLogs([]);
    deployMutation.mutate();
  };

  const handleRollback = (e: React.MouseEvent) => {
    e.preventDefault();
    
    if (!selectedRollbackId) {
      toast({
        title: "Validation Error",
        description: "Please select a deployment to rollback.",
        variant: "destructive",
      });
      return;
    }
    
    const deploymentInfo = selectedDeploymentDetails 
      ? `${selectedDeploymentDetails.ft}/${selectedDeploymentDetails.file}`
      : 'this deployment';
    
    if (window.confirm(`Are you sure you want to rollback ${deploymentInfo}? This will restore the previous version of the file and cannot be undone easily.`)) {
      setFileLogs([]);
      rollbackMutation.mutate(selectedRollbackId);
    }
  };

  const handleRunShellCommand = (e: React.MouseEvent) => {
    e.preventDefault();
    
    if (!shellCommand) {
      toast({
        title: "Validation Error",
        description: "Please enter a shell command.",
        variant: "destructive",
      });
      return;
    }

    if (shellSelectedVMs.length === 0) {
      toast({
        title: "Validation Error",
        description: "Please select at least one VM for shell command.",
        variant: "destructive",
      });
      return;
    }

    setShellLogs([]);
    shellCommandMutation.mutate();
  };

  const formatDeploymentSummary = (deployment: any): string => {
    if (!deployment) return '';
    
    const date = deployment.timestamp ? new Date(deployment.timestamp).toLocaleString() : 'Unknown date';
    const vmCount = deployment.vms ? deployment.vms.length : 0;
    return `${deployment.ft || 'Unknown'}/${deployment.file || 'Unknown'} (${vmCount} VMs) - ${date}`;
  };

  return (

    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-[#F79B72] mb-4">File Operations</h2>

      <div className="space-y-8">
        {/* File Operations Section with Side-by-Side Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* File Deployment Card */}
          <Card className="bg-[#1a2b42] text-[#EEEEEE] border-2 border-[#EEEEEE]/30">
            <CardHeader>
              <CardTitle className="text-[#F79B72]">File Deployment</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* ... keep existing code (all file deployment form fields) */}
              <div>
                <Label htmlFor="ft-select" className="text-[#F79B72]">Select FT</Label>
                <Select value={selectedFt} onValueChange={setSelectedFt}>
                  <SelectTrigger id="ft-select" className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
                    <SelectValue placeholder="Select an FT" />
                  </SelectTrigger>
                  <SelectContent>
                    {fts.map((ft: string) => (
                      <SelectItem key={ft} value={ft}>{ft}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="file-select" className="text-[#F79B72]">Select File</Label>
                <Select 
                  value={selectedFile} 
                  onValueChange={setSelectedFile}
                  disabled={!selectedFt}
                >
                  <SelectTrigger id="file-select" className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
                    <SelectValue placeholder="Select a file" />
                  </SelectTrigger>
                  <SelectContent>
                    {files.map((file: string) => (
                      <SelectItem key={file} value={file}>{file}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="user-select" className="text-[#F79B72]">Select User</Label>
                <Select value={selectedUser} onValueChange={setSelectedUser}>
                  <SelectTrigger id="user-select" className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
                    <SelectValue placeholder="Select a user" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="infadm">infadm</SelectItem>
                    <SelectItem value="abpwrk1">abpwrk1</SelectItem>
                    <SelectItem value="root">root</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="target-path" className="text-[#F79B72]">Target Path</Label>
                <Input 
                  id="target-path" 
                  value={targetPath} 
                  onChange={(e) => setTargetPath(e.target.value)}
                  placeholder="/opt/amdocs/abpwrk1/pbin/app" 
                  className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30"
                />
              </div>

              <div className="flex items-center space-x-2">
                <Checkbox 
                  id="sudo" 
                  checked={useSudo} 
                  onCheckedChange={(checked) => setUseSudo(checked === true)}
                />
                <Label htmlFor="sudo" className="text-[#F79B72]">Use sudo</Label>
              </div>
              
              <div className="flex items-center space-x-2">
                <Checkbox 
                  id="backup" 
                  checked={createBackup} 
                  onCheckedChange={(checked) => setCreateBackup(checked === true)}
                />
                <Label htmlFor="backup" className="text-[#F79B72]">Create backup if file exists</Label>
              </div>

              <div>
                <Label className="block text-[#F79B72] mb-2">Select VMs</Label>
                <VMSelector 
                  onSelectionChange={handleVMSelectionChange}
                  selectedVMs={selectedVMs}
                />
              </div>

              <div className="flex space-x-2">
                <Button 
                  type="button"
                  onClick={handleDeploy} 
                  className="bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
                  disabled={deployMutation.isPending || fileOperationStatus === 'running' || fileOperationStatus === 'loading'}
                >
                  {deployMutation.isPending || fileOperationStatus === 'running' || fileOperationStatus === 'loading' ? 
                    "Deploying..." : "Deploy"}
                </Button>
                
                <div className="flex space-x-2 ml-2">
                  <div className="flex items-center space-x-2">
                    <Checkbox 
                      id="validate-sudo" 
                      checked={validateUseSudo} 
                      onCheckedChange={(checked) => setValidateUseSudo(checked === true)}
                    />
                    <Label htmlFor="validate-sudo" className="text-[#F79B72]">Sudo</Label>
                  </div>
                  <Button 
                    onClick={() => validateMutation.mutate()}
                    className="bg-[#2A4759] hover:bg-[#2A4759]/80 text-[#EEEEEE] border-[#EEEEEE]/30"
                    disabled={!deploymentId || validateMutation.isPending}
                  >
                    {validateMutation.isPending ? "Validating..." : "Validate"}
                  </Button>
                </div>
              </div>
              
              {/* Enhanced Rollback Section */}
              <div className="mt-4 pt-4 border-t border-[#F79B72]/30">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-md font-medium text-[#F79B72]">Rollback Previous Deployment</h4>
                  <div className="flex items-center space-x-2 text-sm text-[#EEEEEE]">
                    <span>({recentFileDeployments.length} available)</span>
                  </div>
                </div>
                
                {/* Auto-refresh controls */}
                <div className="bg-[#2A4759]/50 p-3 rounded mb-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <Checkbox 
                        id="auto-refresh" 
                        checked={autoRefreshEnabled} 
                        onCheckedChange={(checked) => setAutoRefreshEnabled(checked === true)}
                      />
                      <Label htmlFor="auto-refresh" className="text-[#EEEEEE] text-sm">Auto-refresh</Label>
                      {autoRefreshEnabled && (
                        <span className="text-xs text-green-400 font-medium">Active</span>
                      )}
                    </div>
                    <Button 
                      onClick={handleManualRefresh}
                      size="sm"
                      variant="outline"
                      className="h-7 px-2 border-[#F79B72] text-[#F79B72] hover:bg-[#F79B72] hover:text-[#2A4759]"
                      disabled={manualRefreshLoading || isLoadingDeployments}
                    >
                      <RefreshCcw className={`h-3 w-3 ${manualRefreshLoading ? 'animate-spin' : ''}`} />
                    </Button>
                  </div>
                  
                  {autoRefreshEnabled && (
                    <div className="flex items-center space-x-2">
                      <Label className="text-xs text-[#EEEEEE]">Interval:</Label>
                      <Select 
                        value={refreshInterval.toString()} 
                        onValueChange={(value) => setRefreshInterval(parseInt(value))}
                      >
                        <SelectTrigger className="h-6 w-20 text-xs border-[#F79B72]/50 bg-[#1a2b42] text-[#EEEEEE]">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="10000">10s</SelectItem>
                          <SelectItem value="30000">30s</SelectItem>
                          <SelectItem value="60000">1m</SelectItem>
                          <SelectItem value="300000">5m</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  )}
                  
                  {lastRefreshTime && (
                    <div className="text-xs text-[#EEEEEE]/70">
                      Last updated: {lastRefreshTime.toLocaleTimeString()}
                    </div>
                  )}
                </div>

                {/* Error state */}
                {isDeploymentsError && (
                  <div className="bg-red-900/20 border border-red-500/50 p-2 rounded mb-3">
                    <div className="text-sm text-red-400">
                      Failed to load deployments: {deploymentsError instanceof Error ? deploymentsError.message : 'Unknown error'}
                    </div>
                  </div>
                )}

                {/* Enhanced dropdown */}
                <div>
                  <Label htmlFor="rollback-select" className="text-[#F79B72]">Select Deployment</Label>
                  <div className="relative">
                    <Select 
                      value={selectedRollbackId || ''} 
                      onValueChange={handleRollbackSelection}
                      disabled={recentFileDeployments.length === 0 || isLoadingDeployments}
                    >
                      <SelectTrigger 
                        id="rollback-select" 
                        className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30 pr-8"
                      >
                        <SelectValue 
                          placeholder={
                            isLoadingDeployments 
                              ? "Loading deployments..." 
                              : recentFileDeployments.length === 0 
                                ? "No deployments available" 
                                : "Select a deployment"
                          } 
                        />
                      </SelectTrigger>
                      <SelectContent className="max-h-40">
                        {recentFileDeployments.map((deployment) => (
                          <SelectItem key={deployment.id} value={deployment.id} className="text-sm">
                            {formatDeploymentSummary(deployment)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {isLoadingDeployments && (
                      <RefreshCcw className="absolute right-8 top-1/2 transform -translate-y-1/2 h-3 w-3 animate-spin text-[#F79B72]" />
                    )}
                  </div>
                </div>

                {/* Selected deployment details */}
                {selectedDeploymentDetails && (
                  <div className="mt-2 p-2 bg-blue-900/20 border border-blue-500/50 rounded text-xs">
                    <div className="font-medium text-blue-400">Deployment Details:</div>
                    <div className="text-blue-300">
                      <div>FT: {selectedDeploymentDetails.ft}</div>
                      <div>File: {selectedDeploymentDetails.file}</div>
                      <div>User: {selectedDeploymentDetails.user}</div>
                      <div>Target: {selectedDeploymentDetails.targetPath || selectedDeploymentDetails.target_path || 'N/A'}</div>
                      <div>VMs: {selectedDeploymentDetails.vms ? selectedDeploymentDetails.vms.join(', ') : 'N/A'}</div>
                    </div>
                  </div>
                )}

                {/* Warning message */}
                {selectedRollbackId && (
                  <div className="mt-2 p-2 bg-amber-900/20 border border-amber-500/50 rounded text-xs text-amber-300">
                    <strong>Warning:</strong> Rolling back will restore the previous version of the file. This action should be used carefully in production environments.
                  </div>
                )}
                
                <div className="mt-3">
                  <Button 
                    type="button"
                    onClick={handleRollback} 
                    className="bg-[#2A4759] text-[#EEEEEE] hover:bg-[#2A4759]/80 border-[#EEEEEE]/30"
                    disabled={!selectedRollbackId || rollbackMutation.isPending || fileOperationStatus === 'running' || fileOperationStatus === 'loading'}
                  >
                    {rollbackMutation.isPending ? "Rolling Back..." : "Rollback Deployment"}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* File Deployment Logs - Sticky positioning */}
          <div className="lg:sticky lg:top-4 lg:self-start">
            <LogDisplay 
              logs={fileLogs} 
              height="838px"
              fixedHeight={true}
              title="File Deployment Logs"
              status={fileOperationStatus}
            />
          </div>
        </div>

        {/* Shell Command Section with Side-by-Side Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Shell Command Card */}
          <Card className="bg-[#1a2b42] text-[#EEEEEE] border-2 border-[#EEEEEE]/30">
            <CardHeader>
              <CardTitle className="text-[#F79B72]">Shell Command</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="shell-user-select" className="text-[#F79B72]">Select User</Label>
                <Select 
                  value={shellSelectedUser} 
                  onValueChange={(value) => {
                    setShellSelectedUser(value);
                    if (useUserHomePath) {
                      setShellWorkingDir('');
                    }
                  }}
                >
                  <SelectTrigger id="shell-user-select" className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
                    <SelectValue placeholder="Select a user" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="infadm">infadm</SelectItem>
                    <SelectItem value="abpwrk1">abpwrk1</SelectItem>
                    <SelectItem value="root">root</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <div className="flex items-center space-x-2">
                <Checkbox 
                  id="use-home-path" 
                  checked={useUserHomePath} 
                  onCheckedChange={(checked) => {
                    setUseUserHomePath(checked === true);
                    if (checked) {
                      setShellWorkingDir('');
                    }
                  }}
                />
                <Label htmlFor="use-home-path" className="text-[#F79B72]">
                  Use user's home directory ({userHomes[shellSelectedUser] || `/home/${shellSelectedUser}`})
                </Label>
              </div>
              
              <div>
                <Label htmlFor="shell-working-dir" className="text-[#F79B72]">Custom Working Directory</Label>
                <Input 
                  id="shell-working-dir" 
                  value={shellWorkingDir} 
                  onChange={(e) => setShellWorkingDir(e.target.value)}
                  placeholder="/opt/amdocs/scripts" 
                  className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30"
                  disabled={useUserHomePath}
                />
              </div>
              
              <div>
                <Label htmlFor="shell-command" className="text-[#F79B72]">Command</Label>
                <Input 
                  id="shell-command" 
                  value={shellCommand} 
                  onChange={(e) => setShellCommand(e.target.value)}
                  placeholder="touch config.sh" 
                  className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30"
                />
              </div>
              
              <div className="flex items-center space-x-2">
                <Checkbox 
                  id="shell-sudo" 
                  checked={shellUseSudo} 
                  onCheckedChange={(checked) => setShellUseSudo(checked === true)}
                />
                <Label htmlFor="shell-sudo" className="text-[#F79B72]">Use sudo</Label>
              </div>
              
              <div>
                <Label className="block text-[#F79B72] mb-2">Select VMs</Label>
                <VMSelector 
                  onSelectionChange={handleShellVMSelectionChange}
                  selectedVMs={shellSelectedVMs}
                />
              </div>

              <Button 
                type="button"
                onClick={handleRunShellCommand} 
                className="w-full bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
                disabled={shellCommandMutation.isPending || shellOperationStatus === 'running' || shellOperationStatus === 'loading'}
              >
                {shellCommandMutation.isPending || shellOperationStatus === 'running' || shellOperationStatus === 'loading' ? 
                  "Running..." : "Run Command"}
              </Button>
            </CardContent>
          </Card>

          {/* Shell Command Logs */}
          <div>
            <LogDisplay 
              logs={shellLogs} 
              height="528px"
              fixedHeight={true}
              title="Shell Command Logs"
              status={shellOperationStatus}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default FileOperations;
//     <div className="space-y-6">
//       <h2 className="text-2xl font-bold text-[#F79B72] mb-4">File Operations</h2>

//       <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
//         {/* Left Column - Controls */}
//         <div className="space-y-6">
//           {/* File Deployment Section */}
//           <div className="space-y-4 bg-[#1a2b42] p-4 rounded-md">
//             <h3 className="text-lg font-medium text-[#F79B72]">File Deployment</h3>

//             <div>
//               <Label htmlFor="ft-select" className="text-[#F79B72]">Select FT</Label>
//               <Select value={selectedFt} onValueChange={setSelectedFt}>
//                 <SelectTrigger id="ft-select" className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
//                   <SelectValue placeholder="Select an FT" className="text-[#2A4759]" />
//                 </SelectTrigger>
//                 <SelectContent>
//                   {fts.map((ft: string) => (
//                     <SelectItem key={ft} value={ft}>{ft}</SelectItem>
//                   ))}
//                 </SelectContent>
//               </Select>
//             </div>

//             <div>
//               <Label htmlFor="file-select" className="text-[#F79B72]">Select File</Label>
//               <Select 
//                 value={selectedFile} 
//                 onValueChange={setSelectedFile}
//                 disabled={!selectedFt}
//               >
//                 <SelectTrigger id="file-select" className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
//                   <SelectValue placeholder="Select a file" className="text-[#2A4759]" />
//                 </SelectTrigger>
//                 <SelectContent>
//                   {files.map((file: string) => (
//                     <SelectItem key={file} value={file}>{file}</SelectItem>
//                   ))}
//                 </SelectContent>
//               </Select>
//             </div>

//             <div>
//               <Label htmlFor="user-select" className="text-[#F79B72]">Select User</Label>
//               <Select value={selectedUser} onValueChange={setSelectedUser}>
//                 <SelectTrigger id="user-select" className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
//                   <SelectValue placeholder="Select a user" className="text-[#2A4759]" />
//                 </SelectTrigger>
//                 <SelectContent>
//                   <SelectItem value="infadm">infadm</SelectItem>
//                   <SelectItem value="abpwrk1">abpwrk1</SelectItem>
//                   <SelectItem value="root">root</SelectItem>
//                 </SelectContent>
//               </Select>
//             </div>

//             <div>
//               <Label htmlFor="target-path" className="text-[#F79B72]">Target Path</Label>
//               <Input 
//                 id="target-path" 
//                 value={targetPath} 
//                 onChange={(e) => setTargetPath(e.target.value)}
//                 placeholder="/opt/amdocs/abpwrk1/pbin/app" 
//                 className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]"
//               />
//             </div>

//             <div className="flex items-center space-x-2">
//               <Checkbox 
//                 id="sudo" 
//                 checked={useSudo} 
//                 onCheckedChange={(checked) => setUseSudo(checked === true)}
//               />
//               <Label htmlFor="sudo" className="text-[#F79B72]">Use sudo</Label>
//             </div>
            
//             <div className="flex items-center space-x-2">
//               <Checkbox 
//                 id="backup" 
//                 checked={createBackup} 
//                 onCheckedChange={(checked) => setCreateBackup(checked === true)}
//               />
//               <Label htmlFor="backup" className="text-[#F79B72]">Create backup if file exists</Label>
//             </div>

//             <div>
//               <Label className="block text-[#F79B72] mb-2">Select VMs</Label>
//               <VMSelector 
//                 onSelectionChange={handleVMSelectionChange}
//                 selectedVMs={selectedVMs}
//               />
//             </div>

//             <div className="flex space-x-2">
//               <Button 
//                 type="button"
//                 onClick={handleDeploy} 
//                 className="bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
//                 disabled={deployMutation.isPending || fileOperationStatus === 'running' || fileOperationStatus === 'loading'}
//               >
//                 {deployMutation.isPending || fileOperationStatus === 'running' || fileOperationStatus === 'loading' ? 
//                   "Deploying..." : "Deploy"}
//               </Button>
              
//               <div className="flex space-x-2 ml-2">
//                 <div className="flex items-center space-x-2">
//                   <Checkbox 
//                     id="validate-sudo" 
//                     checked={validateUseSudo} 
//                     onCheckedChange={(checked) => setValidateUseSudo(checked === true)}
//                   />
//                   <Label htmlFor="validate-sudo" className="text-[#F79B72]">Sudo</Label>
//                 </div>
//                 <Button 
//                   onClick={() => validateMutation.mutate()}
//                   className="bg-[#2A4759] hover:bg-[#2A4759]/80 text-white"
//                   disabled={!deploymentId || validateMutation.isPending}
//                 >
//                   {validateMutation.isPending ? "Validating..." : "Validate"}
//                 </Button>
//               </div>
//             </div>
            
//             {/* Enhanced Rollback Section */}
//             <div className="mt-4 pt-4 border-t border-[#F79B72]/30">
//               <div className="flex items-center justify-between mb-3">
//                 <h4 className="text-md font-medium text-[#F79B72]">Rollback Previous Deployment</h4>
//                 <div className="flex items-center space-x-2 text-sm text-[#EEEEEE]">
//                   <span>({recentFileDeployments.length} available)</span>
//                 </div>
//               </div>
              
//               {/* Auto-refresh controls */}
//               <div className="bg-[#2A4759]/50 p-3 rounded mb-3 space-y-2">
//                 <div className="flex items-center justify-between">
//                   <div className="flex items-center space-x-2">
//                     <Checkbox 
//                       id="auto-refresh" 
//                       checked={autoRefreshEnabled} 
//                       onCheckedChange={(checked) => setAutoRefreshEnabled(checked === true)}
//                     />
//                     <Label htmlFor="auto-refresh" className="text-[#EEEEEE] text-sm">Auto-refresh</Label>
//                     {autoRefreshEnabled && (
//                       <span className="text-xs text-green-400 font-medium">Active</span>
//                     )}
//                   </div>
//                   <Button 
//                     onClick={handleManualRefresh}
//                     size="sm"
//                     variant="outline"
//                     className="h-7 px-2 border-[#F79B72] text-[#F79B72] hover:bg-[#F79B72] hover:text-[#2A4759]"
//                     disabled={manualRefreshLoading || isLoadingDeployments}
//                   >
//                     <RefreshCcw className={`h-3 w-3 ${manualRefreshLoading ? 'animate-spin' : ''}`} />
//                   </Button>
//                 </div>
                
//                 {autoRefreshEnabled && (
//                   <div className="flex items-center space-x-2">
//                     <Label className="text-xs text-[#EEEEEE]">Interval:</Label>
//                     <Select 
//                       value={refreshInterval.toString()} 
//                       onValueChange={(value) => setRefreshInterval(parseInt(value))}
//                     >
//                       <SelectTrigger className="h-6 w-20 text-xs border-[#F79B72]/50 bg-[#1a2b42] text-[#EEEEEE]">
//                         <SelectValue />
//                       </SelectTrigger>
//                       <SelectContent>
//                         <SelectItem value="10000">10s</SelectItem>
//                         <SelectItem value="30000">30s</SelectItem>
//                         <SelectItem value="60000">1m</SelectItem>
//                         <SelectItem value="300000">5m</SelectItem>
//                       </SelectContent>
//                     </Select>
//                   </div>
//                 )}
                
//                 {lastRefreshTime && (
//                   <div className="text-xs text-[#EEEEEE]/70">
//                     Last updated: {lastRefreshTime.toLocaleTimeString()}
//                   </div>
//                 )}
//               </div>

//               {/* Error state */}
//               {isDeploymentsError && (
//                 <div className="bg-red-900/20 border border-red-500/50 p-2 rounded mb-3">
//                   <div className="text-sm text-red-400">
//                     Failed to load deployments: {deploymentsError instanceof Error ? deploymentsError.message : 'Unknown error'}
//                   </div>
//                 </div>
//               )}

//               {/* Enhanced dropdown */}
//               <div>
//                 <Label htmlFor="rollback-select" className="text-[#F79B72]">Select Deployment</Label>
//                 <div className="relative">
//                   <Select 
//                     value={selectedRollbackId || ''} 
//                     onValueChange={handleRollbackSelection}
//                     disabled={recentFileDeployments.length === 0 || isLoadingDeployments}
//                   >
//                     <SelectTrigger 
//                       id="rollback-select" 
//                       className="bg-[#1a2b42] border-[#F79B72] text-[#EEEEEE] pr-8"
//                     >
//                       <SelectValue 
//                         placeholder={
//                           isLoadingDeployments 
//                             ? "Loading deployments..." 
//                             : recentFileDeployments.length === 0 
//                               ? "No deployments available" 
//                               : "Select a deployment"
//                         } 
//                         className="text-[#EEEEEE]" 
//                       />
//                     </SelectTrigger>
//                     <SelectContent className="max-h-40 bg-[#1a2b42] border-[#F79B72]">
//                       {recentFileDeployments.map((deployment) => (
//                         <SelectItem key={deployment.id} value={deployment.id} className="text-sm text-[#EEEEEE] hover:bg-[#F79B72] hover:text-[#2A4759]">
//                           {formatDeploymentSummary(deployment)}
//                         </SelectItem>
//                       ))}
//                     </SelectContent>
//                   </Select>
//                   {isLoadingDeployments && (
//                     <RefreshCcw className="absolute right-8 top-1/2 transform -translate-y-1/2 h-3 w-3 animate-spin text-[#F79B72]" />
//                   )}
//                 </div>
//               </div>

//               {/* Selected deployment details */}
//               {selectedDeploymentDetails && (
//                 <div className="mt-2 p-2 bg-blue-900/20 border border-blue-500/50 rounded text-xs">
//                   <div className="font-medium text-blue-400">Deployment Details:</div>
//                   <div className="text-blue-300">
//                     <div>FT: {selectedDeploymentDetails.ft}</div>
//                     <div>File: {selectedDeploymentDetails.file}</div>
//                     <div>User: {selectedDeploymentDetails.user}</div>
//                     <div>Target: {selectedDeploymentDetails.targetPath || selectedDeploymentDetails.target_path || 'N/A'}</div>
//                     <div>VMs: {selectedDeploymentDetails.vms ? selectedDeploymentDetails.vms.join(', ') : 'N/A'}</div>
//                   </div>
//                 </div>
//               )}

//               {/* Warning message */}
//               {selectedRollbackId && (
//                 <div className="mt-2 p-2 bg-amber-900/20 border border-amber-500/50 rounded text-xs text-amber-300">
//                   <strong>Warning:</strong> Rolling back will restore the previous version of the file. This action should be used carefully in production environments.
//                 </div>
//               )}
              
//               <div className="mt-3">
//                 <Button 
//                   type="button"
//                   onClick={handleRollback} 
//                   className="bg-[#2A4759] text-white hover:bg-[#2A4759]/80"
//                   disabled={!selectedRollbackId || rollbackMutation.isPending || fileOperationStatus === 'running' || fileOperationStatus === 'loading'}
//                 >
//                   {rollbackMutation.isPending ? "Rolling Back..." : "Rollback Deployment"}
//                 </Button>
//               </div>
//             </div>
//           </div>
          
//           {/* Shell Command Section */}
//           <div className="space-y-4 bg-[#EEEEEE] p-4 rounded-md">
//             <h3 className="text-lg font-medium text-[#F79B72]">Shell Command</h3>
            
//             <div>
//               <Label htmlFor="shell-user-select" className="text-[#F79B72]">Select User</Label>
//               <Select 
//                 value={shellSelectedUser} 
//                 onValueChange={(value) => {
//                   setShellSelectedUser(value);
//                   if (useUserHomePath) {
//                     setShellWorkingDir('');
//                   }
//                 }}
//               >
//                 <SelectTrigger id="shell-user-select" className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
//                   <SelectValue placeholder="Select a user" className="text-[#2A4759]" />
//                 </SelectTrigger>
//                 <SelectContent>
//                   <SelectItem value="infadm">infadm</SelectItem>
//                   <SelectItem value="abpwrk1">abpwrk1</SelectItem>
//                   <SelectItem value="root">root</SelectItem>
//                 </SelectContent>
//               </Select>
//             </div>
            
//             <div className="flex items-center space-x-2">
//               <Checkbox 
//                 id="use-home-path" 
//                 checked={useUserHomePath} 
//                 onCheckedChange={(checked) => {
//                   setUseUserHomePath(checked === true);
//                   if (checked) {
//                     setShellWorkingDir('');
//                   }
//                 }}
//               />
//               <Label htmlFor="use-home-path" className="text-[#F79B72]">
//                 Use user's home directory ({userHomes[shellSelectedUser] || `/home/${shellSelectedUser}`})
//               </Label>
//             </div>
            
//             <div>
//               <Label htmlFor="shell-working-dir" className="text-[#F79B72]">Custom Working Directory</Label>
//               <Input 
//                 id="shell-working-dir" 
//                 value={shellWorkingDir} 
//                 onChange={(e) => setShellWorkingDir(e.target.value)}
//                 placeholder="/opt/amdocs/scripts" 
//                 className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]"
//                 disabled={useUserHomePath}
//               />
//             </div>
            
//             <div>
//               <Label htmlFor="shell-command" className="text-[#F79B72]">Command</Label>
//               <Input 
//                 id="shell-command" 
//                 value={shellCommand} 
//                 onChange={(e) => setShellCommand(e.target.value)}
//                 placeholder="touch config.sh" 
//                 className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]"
//               />
//             </div>
            
//             <div className="flex items-center space-x-2">
//               <Checkbox 
//                 id="shell-sudo" 
//                 checked={shellUseSudo} 
//                 onCheckedChange={(checked) => setShellUseSudo(checked === true)}
//               />
//               <Label htmlFor="shell-sudo" className="text-[#F79B72]">Use sudo</Label>
//             </div>
            
//             <div>
//               <Label className="block text-[#F79B72] mb-2">Select VMs</Label>
//               <VMSelector 
//                 onSelectionChange={handleShellVMSelectionChange}
//                 selectedVMs={shellSelectedVMs}
//               />
//             </div>

//             <Button 
//               type="button"
//               onClick={handleRunShellCommand} 
//               className="bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
//               disabled={shellCommandMutation.isPending || shellOperationStatus === 'running' || shellOperationStatus === 'loading'}
//             >
//               {shellCommandMutation.isPending || shellOperationStatus === 'running' || shellOperationStatus === 'loading' ? 
//                 "Running..." : "Run Command"}
//             </Button>
//           </div>
//         </div>
        
//         {/* Right Column - Logs Section (Fixed Position) */}
//         <div className="space-y-6 sticky top-4">
//           <div>
//             <LogDisplay 
//               logs={fileLogs} 
//               height="528px"
//               fixedHeight={true}
//               title="File Deployment Logs"
//               status={fileOperationStatus}
//               autoScroll={false}
//               fixAutoScroll={true}
//             />
//           </div>
          
//           <div>
//             <LogDisplay 
//               logs={shellLogs} 
//               height="528px"
//               fixedHeight={true}
//               title="Shell Command Logs"
//               status={shellOperationStatus}
//               autoScroll={false}
//               fixAutoScroll={true}
//             />
//           </div>
//         </div>
//       </div>
//     </div>
//   );
// };
// export default FileOperations;

//   const formatDeploymentSummary = (deployment: any): string => {
//     if (!deployment) return '';
    
//     const date = deployment.timestamp ? new Date(deployment.timestamp).toLocaleString() : 'Unknown date';
//     const vmCount = deployment.vms ? deployment.vms.length : 0;
//     return `${deployment.ft || 'Unknown'}/${deployment.file || 'Unknown'} (${vmCount} VMs) - ${date}`;
//   };

//   return (
//     <div className="space-y-6">
//       <h2 className="text-2xl font-bold text-[#F79B72] mb-4">File Operations</h2>

//       <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
//         {/* Left Column - Controls */}
//         <div className="space-y-6">
//           {/* File Deployment Section */}
//           <div className="space-y-4 bg-[#1a2b42] p-4 rounded-md">
//             <h3 className="text-lg font-medium text-[#F79B72]">File Deployment</h3>

//             <div>
//               <Label htmlFor="ft-select" className="text-[#F79B72]">Select FT</Label>
//               <Select value={selectedFt} onValueChange={setSelectedFt}>
//                 <SelectTrigger id="ft-select" className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
//                   <SelectValue placeholder="Select an FT" className="text-[#2A4759]" />
//                 </SelectTrigger>
//                 <SelectContent>
//                   {fts.map((ft: string) => (
//                     <SelectItem key={ft} value={ft}>{ft}</SelectItem>
//                   ))}
//                 </SelectContent>
//               </Select>
//             </div>

//             <div>
//               <Label htmlFor="file-select" className="text-[#F79B72]">Select File</Label>
//               <Select 
//                 value={selectedFile} 
//                 onValueChange={setSelectedFile}
//                 disabled={!selectedFt}
//               >
//                 <SelectTrigger id="file-select" className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
//                   <SelectValue placeholder="Select a file" className="text-[#2A4759]" />
//                 </SelectTrigger>
//                 <SelectContent>
//                   {files.map((file: string) => (
//                     <SelectItem key={file} value={file}>{file}</SelectItem>
//                   ))}
//                 </SelectContent>
//               </Select>
//             </div>

//             <div>
//               <Label htmlFor="user-select" className="text-[#F79B72]">Select User</Label>
//               <Select value={selectedUser} onValueChange={setSelectedUser}>
//                 <SelectTrigger id="user-select" className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
//                   <SelectValue placeholder="Select a user" className="text-[#2A4759]" />
//                 </SelectTrigger>
//                 <SelectContent>
//                   <SelectItem value="infadm">infadm</SelectItem>
//                   <SelectItem value="abpwrk1">abpwrk1</SelectItem>
//                   <SelectItem value="root">root</SelectItem>
//                 </SelectContent>
//               </Select>
//             </div>

//             <div>
//               <Label htmlFor="target-path" className="text-[#F79B72]">Target Path</Label>
//               <Input 
//                 id="target-path" 
//                 value={targetPath} 
//                 onChange={(e) => setTargetPath(e.target.value)}
//                 placeholder="/opt/amdocs/abpwrk1/pbin/app" 
//                 className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]"
//               />
//             </div>

//             <div className="flex items-center space-x-2">
//               <Checkbox 
//                 id="sudo" 
//                 checked={useSudo} 
//                 onCheckedChange={(checked) => setUseSudo(checked === true)}
//               />
//               <Label htmlFor="sudo" className="text-[#F79B72]">Use sudo</Label>
//             </div>
            
//             <div className="flex items-center space-x-2">
//               <Checkbox 
//                 id="backup" 
//                 checked={createBackup} 
//                 onCheckedChange={(checked) => setCreateBackup(checked === true)}
//               />
//               <Label htmlFor="backup" className="text-[#F79B72]">Create backup if file exists</Label>
//             </div>

//             <div>
//               <Label className="block text-[#F79B72] mb-2">Select VMs</Label>
//               <VMSelector 
//                 onSelectionChange={handleVMSelectionChange}
//                 selectedVMs={selectedVMs}
//               />
//             </div>

//             <div className="flex space-x-2">
//               <Button 
//                 type="button"
//                 onClick={handleDeploy} 
//                 className="bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
//                 disabled={deployMutation.isPending || fileOperationStatus === 'running' || fileOperationStatus === 'loading'}
//               >
//                 {deployMutation.isPending || fileOperationStatus === 'running' || fileOperationStatus === 'loading' ? 
//                   "Deploying..." : "Deploy"}
//               </Button>
              
//               <div className="flex space-x-2 ml-2">
//                 <div className="flex items-center space-x-2">
//                   <Checkbox 
//                     id="validate-sudo" 
//                     checked={validateUseSudo} 
//                     onCheckedChange={(checked) => setValidateUseSudo(checked === true)}
//                   />
//                   <Label htmlFor="validate-sudo" className="text-[#F79B72]">Sudo</Label>
//                 </div>
//                 <Button 
//                   onClick={() => validateMutation.mutate()}
//                   className="bg-[#2A4759] hover:bg-[#2A4759]/80 text-white"
//                   disabled={!deploymentId || validateMutation.isPending}
//                 >
//                   {validateMutation.isPending ? "Validating..." : "Validate"}
//                 </Button>
//               </div>
//             </div>
            
//             {/* Enhanced Rollback Section */}
//             <div className="mt-4 pt-4 border-t border-[#F79B72]/30">
//               <div className="flex items-center justify-between mb-3">
//                 <h4 className="text-md font-medium text-[#F79B72]">Rollback Previous Deployment</h4>
//                 <div className="flex items-center space-x-2 text-sm text-[#EEEEEE]">
//                   <span>({recentFileDeployments.length} available)</span>
//                 </div>
//               </div>
              
//               {/* Auto-refresh controls */}
//               <div className="bg-[#2A4759]/50 p-3 rounded mb-3 space-y-2">
//                 <div className="flex items-center justify-between">
//                   <div className="flex items-center space-x-2">
//                     <Checkbox 
//                       id="auto-refresh" 
//                       checked={autoRefreshEnabled} 
//                       onCheckedChange={(checked) => setAutoRefreshEnabled(checked === true)}
//                     />
//                     <Label htmlFor="auto-refresh" className="text-[#EEEEEE] text-sm">Auto-refresh</Label>
//                     {autoRefreshEnabled && (
//                       <span className="text-xs text-green-400 font-medium">Active</span>
//                     )}
//                   </div>
//                   <Button 
//                     onClick={handleManualRefresh}
//                     size="sm"
//                     variant="outline"
//                     className="h-7 px-2 border-[#F79B72] text-[#F79B72] hover:bg-[#F79B72] hover:text-[#2A4759]"
//                     disabled={manualRefreshLoading || isLoadingDeployments}
//                   >
//                     <RefreshCcw className={`h-3 w-3 ${manualRefreshLoading ? 'animate-spin' : ''}`} />
//                   </Button>
//                 </div>
                
//                 {autoRefreshEnabled && (
//                   <div className="flex items-center space-x-2">
//                     <Label className="text-xs text-[#EEEEEE]">Interval:</Label>
//                     <Select 
//                       value={refreshInterval.toString()} 
//                       onValueChange={(value) => setRefreshInterval(parseInt(value))}
//                     >
//                       <SelectTrigger className="h-6 w-20 text-xs border-[#F79B72]/50 bg-[#1a2b42] text-[#EEEEEE]">
//                         <SelectValue />
//                       </SelectTrigger>
//                       <SelectContent>
//                         <SelectItem value="10000">10s</SelectItem>
//                         <SelectItem value="30000">30s</SelectItem>
//                         <SelectItem value="60000">1m</SelectItem>
//                         <SelectItem value="300000">5m</SelectItem>
//                       </SelectContent>
//                     </Select>
//                   </div>
//                 )}
                
//                 {lastRefreshTime && (
//                   <div className="text-xs text-[#EEEEEE]/70">
//                     Last updated: {lastRefreshTime.toLocaleTimeString()}
//                   </div>
//                 )}
//               </div>

//               {/* Error state */}
//               {isDeploymentsError && (
//                 <div className="bg-red-900/20 border border-red-500/50 p-2 rounded mb-3">
//                   <div className="text-sm text-red-400">
//                     Failed to load deployments: {deploymentsError instanceof Error ? deploymentsError.message : 'Unknown error'}
//                   </div>
//                 </div>
//               )}

//               {/* Enhanced dropdown */}
//               <div>
//                 <Label htmlFor="rollback-select" className="text-[#F79B72]">Select Deployment</Label>
//                 <div className="relative">
//                   <Select 
//                     value={selectedRollbackId || ''} 
//                     onValueChange={handleRollbackSelection}
//                     disabled={recentFileDeployments.length === 0 || isLoadingDeployments}
//                   >
//                     <SelectTrigger 
//                       id="rollback-select" 
//                       className="bg-[#1a2b42] border-[#F79B72] text-[#EEEEEE] pr-8"
//                     >
//                       <SelectValue 
//                         placeholder={
//                           isLoadingDeployments 
//                             ? "Loading deployments..." 
//                             : recentFileDeployments.length === 0 
//                               ? "No deployments available" 
//                               : "Select a deployment"
//                         } 
//                         className="text-[#EEEEEE]" 
//                       />
//                     </SelectTrigger>
//                     <SelectContent className="max-h-40 bg-[#1a2b42] border-[#F79B72]">
//                       {recentFileDeployments.map((deployment) => (
//                         <SelectItem key={deployment.id} value={deployment.id} className="text-sm text-[#EEEEEE] hover:bg-[#F79B72] hover:text-[#2A4759]">
//                           {formatDeploymentSummary(deployment)}
//                         </SelectItem>
//                       ))}
//                     </SelectContent>
//                   </Select>
//                   {isLoadingDeployments && (
//                     <RefreshCcw className="absolute right-8 top-1/2 transform -translate-y-1/2 h-3 w-3 animate-spin text-[#F79B72]" />
//                   )}
//                 </div>
//               </div>

//               {/* Selected deployment details */}
//               {selectedDeploymentDetails && (
//                 <div className="mt-2 p-2 bg-blue-900/20 border border-blue-500/50 rounded text-xs">
//                   <div className="font-medium text-blue-400">Deployment Details:</div>
//                   <div className="text-blue-300">
//                     <div>FT: {selectedDeploymentDetails.ft}</div>
//                     <div>File: {selectedDeploymentDetails.file}</div>
//                     <div>User: {selectedDeploymentDetails.user}</div>
//                     <div>Target: {selectedDeploymentDetails.targetPath || selectedDeploymentDetails.target_path || 'N/A'}</div>
//                     <div>VMs: {selectedDeploymentDetails.vms ? selectedDeploymentDetails.vms.join(', ') : 'N/A'}</div>
//                   </div>
//                 </div>
//               )}

//               {/* Warning message */}
//               {selectedRollbackId && (
//                 <div className="mt-2 p-2 bg-amber-900/20 border border-amber-500/50 rounded text-xs text-amber-300">
//                   <strong>Warning:</strong> Rolling back will restore the previous version of the file. This action should be used carefully in production environments.
//                 </div>
//               )}
              
//               <div className="mt-3">
//                 <Button 
//                   type="button"
//                   onClick={handleRollback} 
//                   className="bg-[#2A4759] text-white hover:bg-[#2A4759]/80"
//                   disabled={!selectedRollbackId || rollbackMutation.isPending || fileOperationStatus === 'running' || fileOperationStatus === 'loading'}
//                 >
//                   {rollbackMutation.isPending ? "Rolling Back..." : "Rollback Deployment"}
//                 </Button>
//               </div>
//             </div>
//           </div>
          
//           {/* Shell Command Section */}
//           <div className="space-y-4 bg-[#EEEEEE] p-4 rounded-md">
//             <h3 className="text-lg font-medium text-[#F79B72]">Shell Command</h3>
            
//             <div>
//               <Label htmlFor="shell-user-select" className="text-[#F79B72]">Select User</Label>
//               <Select 
//                 value={shellSelectedUser} 
//                 onValueChange={(value) => {
//                   setShellSelectedUser(value);
//                   if (useUserHomePath) {
//                     setShellWorkingDir('');
//                   }
//                 }}
//               >
//                 <SelectTrigger id="shell-user-select" className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
//                   <SelectValue placeholder="Select a user" className="text-[#2A4759]" />
//                 </SelectTrigger>
//                 <SelectContent>
//                   <SelectItem value="infadm">infadm</SelectItem>
//                   <SelectItem value="abpwrk1">abpwrk1</SelectItem>
//                   <SelectItem value="root">root</SelectItem>
//                 </SelectContent>
//               </Select>
//             </div>
            
//             <div className="flex items-center space-x-2">
//               <Checkbox 
//                 id="use-home-path" 
//                 checked={useUserHomePath} 
//                 onCheckedChange={(checked) => {
//                   setUseUserHomePath(checked === true);
//                   if (checked) {
//                     setShellWorkingDir('');
//                   }
//                 }}
//               />
//               <Label htmlFor="use-home-path" className="text-[#F79B72]">
//                 Use user's home directory ({userHomes[shellSelectedUser] || `/home/${shellSelectedUser}`})
//               </Label>
//             </div>
            
//             <div>
//               <Label htmlFor="shell-working-dir" className="text-[#F79B72]">Custom Working Directory</Label>
//               <Input 
//                 id="shell-working-dir" 
//                 value={shellWorkingDir} 
//                 onChange={(e) => setShellWorkingDir(e.target.value)}
//                 placeholder="/opt/amdocs/scripts" 
//                 className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]"
//                 disabled={useUserHomePath}
//               />
//             </div>
            
//             <div>
//               <Label htmlFor="shell-command" className="text-[#F79B72]">Command</Label>
//               <Input 
//                 id="shell-command" 
//                 value={shellCommand} 
//                 onChange={(e) => setShellCommand(e.target.value)}
//                 placeholder="touch config.sh" 
//                 className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]"
//               />
//             </div>
            
//             <div className="flex items-center space-x-2">
//               <Checkbox 
//                 id="shell-sudo" 
//                 checked={shellUseSudo} 
//                 onCheckedChange={(checked) => setShellUseSudo(checked === true)}
//               />
//               <Label htmlFor="shell-sudo" className="text-[#F79B72]">Use sudo</Label>
//             </div>
            
//             <div>
//               <Label className="block text-[#F79B72] mb-2">Select VMs</Label>
//               <VMSelector 
//                 onSelectionChange={handleShellVMSelectionChange}
//                 selectedVMs={shellSelectedVMs}
//               />
//             </div>

//             <Button 
//               type="button"
//               onClick={handleRunShellCommand} 
//               className="bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
//               disabled={shellCommandMutation.isPending || shellOperationStatus === 'running' || shellOperationStatus === 'loading'}
//             >
//               {shellCommandMutation.isPending || shellOperationStatus === 'running' || shellOperationStatus === 'loading' ? 
//                 "Running..." : "Run Command"}
//             </Button>
//           </div>
//         </div>
        
//         {/* Right Column - Logs Section (Fixed Position) */}
//         <div className="space-y-6 sticky top-0">
//           <div>
//             <LogDisplay 
//               logs={fileLogs} 
//               height="400px"
//               fixedHeight={true}
//               title="File Deployment Logs"
//               status={fileOperationStatus}
//             />
//           </div>
          
//           <div>
//             <LogDisplay 
//               logs={shellLogs} 
//               height="400px"
//               fixedHeight={true}
//               title="Shell Command Logs"
//               status={shellOperationStatus}
//             />
//           </div>
//         </div>
//       </div>
//     </div>
//   );
// };
//  export default FileOperations;


//   const formatDeploymentSummary = (deployment: any): string => {
//     if (!deployment) return '';
    
//     const date = deployment.timestamp ? new Date(deployment.timestamp).toLocaleString() : 'Unknown date';
//     const vmCount = deployment.vms ? deployment.vms.length : 0;
//     return `${deployment.ft || 'Unknown'}/${deployment.file || 'Unknown'} (${vmCount} VMs) - ${date}`;
//   };

//   return (
//     <div className="space-y-6">
//       <h2 className="text-2xl font-bold text-[#F79B72] mb-4">File Operations</h2>

//       <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
//         <div className="space-y-6">
//           {/* File Deployment Section */}
//           <div className="space-y-4 bg-[#1a2b42] p-4 rounded-md">
//             <h3 className="text-lg font-medium text-[#F79B72]">File Deployment</h3>

//             <div>
//               <Label htmlFor="ft-select" className="text-[#F79B72]">Select FT</Label>
//               <Select value={selectedFt} onValueChange={setSelectedFt}>
//                 <SelectTrigger id="ft-select" className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
//                   <SelectValue placeholder="Select an FT" className="text-[#2A4759]" />
//                 </SelectTrigger>
//                 <SelectContent>
//                   {fts.map((ft: string) => (
//                     <SelectItem key={ft} value={ft}>{ft}</SelectItem>
//                   ))}
//                 </SelectContent>
//               </Select>
//             </div>

//             <div>
//               <Label htmlFor="file-select" className="text-[#F79B72]">Select File</Label>
//               <Select 
//                 value={selectedFile} 
//                 onValueChange={setSelectedFile}
//                 disabled={!selectedFt}
//               >
//                 <SelectTrigger id="file-select" className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
//                   <SelectValue placeholder="Select a file" className="text-[#2A4759]" />
//                 </SelectTrigger>
//                 <SelectContent>
//                   {files.map((file: string) => (
//                     <SelectItem key={file} value={file}>{file}</SelectItem>
//                   ))}
//                 </SelectContent>
//               </Select>
//             </div>

//             <div>
//               <Label htmlFor="user-select" className="text-[#F79B72]">Select User</Label>
//               <Select value={selectedUser} onValueChange={setSelectedUser}>
//                 <SelectTrigger id="user-select" className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
//                   <SelectValue placeholder="Select a user" className="text-[#2A4759]" />
//                 </SelectTrigger>
//                 <SelectContent>
//                   <SelectItem value="infadm">infadm</SelectItem>
//                   <SelectItem value="abpwrk1">abpwrk1</SelectItem>
//                   <SelectItem value="root">root</SelectItem>
//                 </SelectContent>
//               </Select>
//             </div>

//             <div>
//               <Label htmlFor="target-path" className="text-[#F79B72]">Target Path</Label>
//               <Input 
//                 id="target-path" 
//                 value={targetPath} 
//                 onChange={(e) => setTargetPath(e.target.value)}
//                 placeholder="/opt/amdocs/abpwrk1/pbin/app" 
//                 className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]"
//               />
//             </div>

//             <div className="flex items-center space-x-2">
//               <Checkbox 
//                 id="sudo" 
//                 checked={useSudo} 
//                 onCheckedChange={(checked) => setUseSudo(checked === true)}
//               />
//               <Label htmlFor="sudo" className="text-[#F79B72]">Use sudo</Label>
//             </div>
            
//             <div className="flex items-center space-x-2">
//               <Checkbox 
//                 id="backup" 
//                 checked={createBackup} 
//                 onCheckedChange={(checked) => setCreateBackup(checked === true)}
//               />
//               <Label htmlFor="backup" className="text-[#F79B72]">Create backup if file exists</Label>
//             </div>

//             <div>
//               <Label className="block text-[#F79B72] mb-2">Select VMs</Label>
//               <VMSelector 
//                 onSelectionChange={handleVMSelectionChange}
//                 selectedVMs={selectedVMs}
//               />
//             </div>

//             <div className="flex space-x-2">
//               <Button 
//                 type="button"
//                 onClick={handleDeploy} 
//                 className="bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
//                 disabled={deployMutation.isPending || fileOperationStatus === 'running' || fileOperationStatus === 'loading'}
//               >
//                 {deployMutation.isPending || fileOperationStatus === 'running' || fileOperationStatus === 'loading' ? 
//                   "Deploying..." : "Deploy"}
//               </Button>
              
//               <div className="flex space-x-2 ml-2">
//                 <div className="flex items-center space-x-2">
//                   <Checkbox 
//                     id="validate-sudo" 
//                     checked={validateUseSudo} 
//                     onCheckedChange={(checked) => setValidateUseSudo(checked === true)}
//                   />
//                   <Label htmlFor="validate-sudo" className="text-[#F79B72]">Sudo</Label>
//                 </div>
//                 <Button 
//                   onClick={() => validateMutation.mutate()}
//                   className="bg-[#2A4759] hover:bg-[#2A4759]/80 text-white"
//                   disabled={!deploymentId || validateMutation.isPending}
//                 >
//                   {validateMutation.isPending ? "Validating..." : "Validate"}
//                 </Button>
//               </div>
//             </div>
            
//             {/* Enhanced Rollback Section */}
//             <div className="mt-4 pt-4 border-t border-[#F79B72]/30">
//               <div className="flex items-center justify-between mb-3">
//                 <h4 className="text-md font-medium text-[#F79B72]">Rollback Previous Deployment</h4>
//                 <div className="flex items-center space-x-2 text-sm text-[#EEEEEE]">
//                   <span>({recentFileDeployments.length} available)</span>
//                 </div>
//               </div>
              
//               {/* Auto-refresh controls */}
//               <div className="bg-[#2A4759]/50 p-3 rounded mb-3 space-y-2">
//                 <div className="flex items-center justify-between">
//                   <div className="flex items-center space-x-2">
//                     <Checkbox 
//                       id="auto-refresh" 
//                       checked={autoRefreshEnabled} 
//                       onCheckedChange={(checked) => setAutoRefreshEnabled(checked === true)}
//                     />
//                     <Label htmlFor="auto-refresh" className="text-[#EEEEEE] text-sm">Auto-refresh</Label>
//                     {autoRefreshEnabled && (
//                       <span className="text-xs text-green-400 font-medium">Active</span>
//                     )}
//                   </div>
//                   <Button 
//                     onClick={handleManualRefresh}
//                     size="sm"
//                     variant="outline"
//                     className="h-7 px-2 border-[#F79B72] text-[#F79B72] hover:bg-[#F79B72] hover:text-[#2A4759]"
//                     disabled={manualRefreshLoading || isLoadingDeployments}
//                   >
//                     <RefreshCcw className={`h-3 w-3 ${manualRefreshLoading ? 'animate-spin' : ''}`} />
//                   </Button>
//                 </div>
                
//                 {autoRefreshEnabled && (
//                   <div className="flex items-center space-x-2">
//                     <Label className="text-xs text-[#EEEEEE]">Interval:</Label>
//                     <Select 
//                       value={refreshInterval.toString()} 
//                       onValueChange={(value) => setRefreshInterval(parseInt(value))}
//                     >
//                       <SelectTrigger className="h-6 w-20 text-xs border-[#F79B72]/50 bg-[#1a2b42] text-[#EEEEEE]">
//                         <SelectValue />
//                       </SelectTrigger>
//                       <SelectContent>
//                         <SelectItem value="10000">10s</SelectItem>
//                         <SelectItem value="30000">30s</SelectItem>
//                         <SelectItem value="60000">1m</SelectItem>
//                         <SelectItem value="300000">5m</SelectItem>
//                       </SelectContent>
//                     </Select>
//                   </div>
//                 )}
                
//                 {lastRefreshTime && (
//                   <div className="text-xs text-[#EEEEEE]/70">
//                     Last updated: {lastRefreshTime.toLocaleTimeString()}
//                   </div>
//                 )}
//               </div>

//               {/* Error state */}
//               {isDeploymentsError && (
//                 <div className="bg-red-900/20 border border-red-500/50 p-2 rounded mb-3">
//                   <div className="text-sm text-red-400">
//                     Failed to load deployments: {deploymentsError instanceof Error ? deploymentsError.message : 'Unknown error'}
//                   </div>
//                 </div>
//               )}

//               {/* Enhanced dropdown */}
//               <div>
//                 <Label htmlFor="rollback-select" className="text-[#F79B72]">Select Deployment</Label>
//                 <div className="relative">
//                   <Select 
//                     value={selectedRollbackId || ''} 
//                     onValueChange={handleRollbackSelection}
//                     disabled={recentFileDeployments.length === 0 || isLoadingDeployments}
//                   >
//                     <SelectTrigger 
//                       id="rollback-select" 
//                       className="bg-[#1a2b42] border-[#F79B72] text-[#EEEEEE] pr-8"
//                     >
//                       <SelectValue 
//                         placeholder={
//                           isLoadingDeployments 
//                             ? "Loading deployments..." 
//                             : recentFileDeployments.length === 0 
//                               ? "No deployments available" 
//                               : "Select a deployment"
//                         } 
//                         className="text-[#EEEEEE]" 
//                       />
//                     </SelectTrigger>
//                     <SelectContent className="max-h-40 bg-[#1a2b42] border-[#F79B72]">
//                       {recentFileDeployments.map((deployment) => (
//                         <SelectItem key={deployment.id} value={deployment.id} className="text-sm text-[#EEEEEE] hover:bg-[#F79B72] hover:text-[#2A4759]">
//                           {formatDeploymentSummary(deployment)}
//                         </SelectItem>
//                       ))}
//                     </SelectContent>
//                   </Select>
//                   {isLoadingDeployments && (
//                     <RefreshCcw className="absolute right-8 top-1/2 transform -translate-y-1/2 h-3 w-3 animate-spin text-[#F79B72]" />
//                   )}
//                 </div>
//               </div>

//               {/* Selected deployment details */}
//               {selectedDeploymentDetails && (
//                 <div className="mt-2 p-2 bg-blue-900/20 border border-blue-500/50 rounded text-xs">
//                   <div className="font-medium text-blue-400">Deployment Details:</div>
//                   <div className="text-blue-300">
//                     <div>FT: {selectedDeploymentDetails.ft}</div>
//                     <div>File: {selectedDeploymentDetails.file}</div>
//                     <div>User: {selectedDeploymentDetails.user}</div>
//                     <div>Target: {selectedDeploymentDetails.targetPath || selectedDeploymentDetails.target_path || 'N/A'}</div>
//                     <div>VMs: {selectedDeploymentDetails.vms ? selectedDeploymentDetails.vms.join(', ') : 'N/A'}</div>
//                   </div>
//                 </div>
//               )}

//               {/* Warning message */}
//               {selectedRollbackId && (
//                 <div className="mt-2 p-2 bg-amber-900/20 border border-amber-500/50 rounded text-xs text-amber-300">
//                   <strong>Warning:</strong> Rolling back will restore the previous version of the file. This action should be used carefully in production environments.
//                 </div>
//               )}
              
//               <div className="mt-3">
//                 <Button 
//                   type="button"
//                   onClick={handleRollback} 
//                   className="bg-[#2A4759] text-white hover:bg-[#2A4759]/80"
//                   disabled={!selectedRollbackId || rollbackMutation.isPending || fileOperationStatus === 'running' || fileOperationStatus === 'loading'}
//                 >
//                   {rollbackMutation.isPending ? "Rolling Back..." : "Rollback Deployment"}
//                 </Button>
//               </div>
//             </div>
//           </div>
          
//           {/* Shell Command Section */}
//           <div className="space-y-4 bg-[#EEEEEE] p-4 rounded-md">
//             <h3 className="text-lg font-medium text-[#F79B72]">Shell Command</h3>
            
//             <div>
//               <Label htmlFor="shell-user-select" className="text-[#F79B72]">Select User</Label>
//               <Select 
//                 value={shellSelectedUser} 
//                 onValueChange={(value) => {
//                   setShellSelectedUser(value);
//                   if (useUserHomePath) {
//                     setShellWorkingDir('');
//                   }
//                 }}
//               >
//                 <SelectTrigger id="shell-user-select" className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
//                   <SelectValue placeholder="Select a user" className="text-[#2A4759]" />
//                 </SelectTrigger>
//                 <SelectContent>
//                   <SelectItem value="infadm">infadm</SelectItem>
//                   <SelectItem value="abpwrk1">abpwrk1</SelectItem>
//                   <SelectItem value="root">root</SelectItem>
//                 </SelectContent>
//               </Select>
//             </div>
            
//             <div className="flex items-center space-x-2">
//               <Checkbox 
//                 id="use-home-path" 
//                 checked={useUserHomePath} 
//                 onCheckedChange={(checked) => {
//                   setUseUserHomePath(checked === true);
//                   if (checked) {
//                     setShellWorkingDir('');
//                   }
//                 }}
//               />
//               <Label htmlFor="use-home-path" className="text-[#F79B72]">
//                 Use user's home directory ({userHomes[shellSelectedUser] || `/home/${shellSelectedUser}`})
//               </Label>
//             </div>
            
//             <div>
//               <Label htmlFor="shell-working-dir" className="text-[#F79B72]">Custom Working Directory</Label>
//               <Input 
//                 id="shell-working-dir" 
//                 value={shellWorkingDir} 
//                 onChange={(e) => setShellWorkingDir(e.target.value)}
//                 placeholder="/opt/amdocs/scripts" 
//                 className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]"
//                 disabled={useUserHomePath}
//               />
//             </div>
            
//             <div>
//               <Label htmlFor="shell-command" className="text-[#F79B72]">Command</Label>
//               <Input 
//                 id="shell-command" 
//                 value={shellCommand} 
//                 onChange={(e) => setShellCommand(e.target.value)}
//                 placeholder="touch config.sh" 
//                 className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]"
//               />
//             </div>
            
//             <div className="flex items-center space-x-2">
//               <Checkbox 
//                 id="shell-sudo" 
//                 checked={shellUseSudo} 
//                 onCheckedChange={(checked) => setShellUseSudo(checked === true)}
//               />
//               <Label htmlFor="shell-sudo" className="text-[#F79B72]">Use sudo</Label>
//             </div>
            
//             <div>
//               <Label className="block text-[#F79B72] mb-2">Select VMs</Label>
//               <VMSelector 
//                 onSelectionChange={handleShellVMSelectionChange}
//                 selectedVMs={shellSelectedVMs}
//               />
//             </div>

//             <Button 
//               type="button"
//               onClick={handleRunShellCommand} 
//               className="bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
//               disabled={shellCommandMutation.isPending || shellOperationStatus === 'running' || shellOperationStatus === 'loading'}
//             >
//               {shellCommandMutation.isPending || shellOperationStatus === 'running' || shellOperationStatus === 'loading' ? 
//                 "Running..." : "Run Command"}
//             </Button>
//           </div>
//         </div>
        
//         {/* Logs Section */}
//         <div className="space-y-6">
//           <div>
//             <LogDisplay 
//               logs={fileLogs} 
//               height="345px"
//               fixedHeight={true}
//               title="File Deployment Logs"
//               status={fileOperationStatus}
//             />
//           </div>
          
//           <div>
//             <LogDisplay 
//               logs={shellLogs} 
//               height="485px"
//               fixedHeight={true}
//               title="Shell Command Logs"
//               status={shellOperationStatus}
//             />
//           </div>
//         </div>
//       </div>
//     </div>
//   );
// };



