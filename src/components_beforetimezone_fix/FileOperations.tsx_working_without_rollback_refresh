import React, { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useQuery, useMutation } from '@tanstack/react-query';
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from "@/components/ui/select";
import LogDisplay from '@/components/LogDisplay';
import VMSelector from '@/components/VMSelector';

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
    'infadm': '/home/infadm',
    'abpwrk1': '/home/abpwrk1',
    'root': '/root'
  });

  // New state for managing rollbacks
  const [lastDeployments, setLastDeployments] = useState<any[]>([]);
  const [selectedRollbackId, setSelectedRollbackId] = useState<string | null>(null);

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

  // Fetch recent file deployments for rollback (new query)

  const {
    data: recentFileDeployments = [],
    refetch: refetchRecentFileDeployments,
  } = useQuery({
    queryKey: ['recent-file-deployments'],
    queryFn: async () => {
      try {
        const response = await fetch('/api/deployments/files/recent');
        if (!response.ok) {
          console.error(`Failed to fetch recent deployments: ${await response.text()}`);
          return [];
        }
        const data = await response.json();
        return data
          .filter((deployment: any) => 
            deployment.type === 'file' && deployment.status === 'success'
          )
          .slice(0, 10); // Get last 10 successful file deployments
      } catch (error) {
        console.error('Error fetching recent deployments:', error);
        return [];
      }
    },
    refetchOnWindowFocus: false,
    staleTime: 300000, // 5 minutes
  });
  // const { data: recentFileDeployments = [] } = useQuery({
  //   queryKey: ['recent-file-deployments'],
  //   queryFn: async () => {
  //     try {
  //       const response = await fetch('/api/deployments/files/recent');
  //       if (!response.ok) {
  //         console.error(`Failed to fetch recent deployments: ${await response.text()}`);
  //         return [];
  //       }
  //       const data = await response.json();
  //       return data.filter((deployment: any) => 
  //         deployment.type === 'file' && deployment.status === 'success'
  //       ).slice(0, 10); // Get last 10 successful file deployments
  //     } catch (error) {
  //       console.error('Error fetching recent deployments:', error);
  //       return [];
  //     }
  //   },
  //   refetchOnWindowFocus: false,
  //   staleTime: 300000, // 5 minutes
  // });
  
  // Update lastDeployments when recentFileDeployments changes
  useEffect(() => {
    if (recentFileDeployments && recentFileDeployments.length > 0) {
      setLastDeployments(recentFileDeployments);
    }
  }, [recentFileDeployments]);

  // Deploy mutation
  const deployMutation = useMutation({
    mutationFn: async () => {
      setFileOperationStatus('loading');
      const response = await fetch('/api/deploy/file', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
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
      
      if (!response.ok) {
        throw new Error('Failed to deploy');
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
      
      // Start polling for logs
      pollLogs(data.deploymentId, setFileLogs, setFileOperationStatus);
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

  // Rollback mutation (newly added)
  const rollbackMutation = useMutation({
    mutationFn: async (deploymentId: string) => {
      setFileOperationStatus('loading');
      const response = await fetch(`/api/deploy/${deploymentId}/rollback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      });
      
      if (!response.ok) {
        throw new Error('Failed to rollback deployment');
      }
      
      const data = await response.json();
      setDeploymentId(data.deploymentId);
      setFileOperationStatus('running');
      return data;
    },
    onSuccess: (data) => {
      toast({
        title: "Rollback Started",
        description: "File rollback has been initiated.",
      });
      
      // Start polling for logs
      pollLogs(data.deploymentId, setFileLogs, setFileOperationStatus);
      
      // Clear rollback selection after initiating
      setSelectedRollbackId(null);
    },
    onError: (error) => {
      setFileOperationStatus('failed');
      toast({
        title: "Rollback Failed",
        description: error instanceof Error ? error.message : "An unknown error occurred",
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
        throw new Error('Validation failed');
      }
      
      return response.json();
    },
    onSuccess: (data) => {
      toast({
        title: "Validation Complete",
        description: "File checksum validation has been completed.",
      });
      // Add validation results to logs
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
        description: error instanceof Error ? error.message : "An unknown error occurred",
        variant: "destructive",
      });
    },
  });

  // Run shell command mutation
  const shellCommandMutation = useMutation({
    mutationFn: async () => {
      setShellOperationStatus('loading');
      
      // Determine the working directory
      let workingDirectory = shellWorkingDir;
      
      if (useUserHomePath && !shellWorkingDir) {
        workingDirectory = userHomes[shellSelectedUser] || `/home/${shellSelectedUser}`;
      }
      
      const response = await fetch('/api/command/shell', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
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
      
      // Start polling for logs
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
    
    // Start with a clear log display
    logSetter([]);
    statusSetter('running');
    
    let pollCount = 0;
    let lastLogLength = 0;
    
    // Set up polling interval
    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`/api/deploy/${id}/logs`);
        if (!response.ok) {
          throw new Error('Failed to fetch logs');
        }
        
        const data = await response.json();
        if (data.logs) {
          logSetter(data.logs);
          
          // Check if operation is explicitly complete
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
          
          // Check for implicit completion (logs not changing)
          if (data.logs.length === lastLogLength) {
            pollCount++;
            if (pollCount >= 5) { // After 5 consecutive polls with no changes
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
        
        // Stop polling after 2 minutes as a safeguard
        if (pollCount > 120) {
          console.log('Operation timed out after 2 minutes');
          statusSetter(data.status === 'running' ? 'running' : 'completed');
          clearInterval(pollInterval);
        }
      } catch (error) {
        console.error('Error fetching logs:', error);
        // Don't clear interval yet, try a few more times
        pollCount += 5;
        if (pollCount > 20) {  // After several failures, give up
          statusSetter('failed');
          clearInterval(pollInterval);
        }
      }
    }, 1000); // Poll every second
    
    // Clean up on unmount
    return () => {
      clearInterval(pollInterval);
    };
  };

  // Handle VM selection changes for file operations
  const handleVMSelectionChange = (vms: string[]) => {
    setSelectedVMs(vms);
  };
  
  // Handle VM selection changes for shell operations
  const handleShellVMSelectionChange = (vms: string[]) => {
    setShellSelectedVMs(vms);
  };

  const handleDeploy = (e: React.MouseEvent) => {
    e.preventDefault(); // Prevent the default action
    
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

  // New function to handle rollback
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
    
    if (window.confirm("Are you sure you want to rollback this deployment? This will restore the previous version of the file.")) {
      setFileLogs([]);
      rollbackMutation.mutate(selectedRollbackId);
    }
  };

  const handleRunShellCommand = (e: React.MouseEvent) => {
    e.preventDefault(); // Prevent the default action
    
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

  // Format the deployment summary for the rollback dropdown
  const formatDeploymentSummary = (deployment: any): string => {
    if (!deployment) return '';
    
    const date = deployment.timestamp ? new Date(deployment.timestamp).toLocaleString() : 'Unknown date';
    return `${deployment.ft || 'Unknown'}/${deployment.file || 'Unknown'} - ${date}`;
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-[#F79B72] mb-4">File Operations</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-6">
          {/* File Deployment Section */}
          <div className="space-y-4 bg-[#EEEEEE] p-4 rounded-md">
            <h3 className="text-lg font-medium text-[#F79B72]">File Deployment</h3>

            <div>
              <Label htmlFor="ft-select" className="text-[#F79B72]">Select FT</Label>
              <Select value={selectedFt} onValueChange={setSelectedFt}>
                <SelectTrigger id="ft-select" className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
                  <SelectValue placeholder="Select an FT" className="text-[#2A4759]" />
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
                <SelectTrigger id="file-select" className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
                  <SelectValue placeholder="Select a file" className="text-[#2A4759]" />
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
                <SelectTrigger id="user-select" className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
                  <SelectValue placeholder="Select a user" className="text-[#2A4759]" />
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
                className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]"
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
                  className="bg-[#2A4759] hover:bg-[#2A4759]/80 text-white"
                  disabled={!deploymentId || validateMutation.isPending}
                >
                  Validate
                </Button>
              </div>
            </div>
            
            {/* New Rollback Section */}
            <div className="mt-4 pt-4 border-t border-[#2A4759]/30">
              <h4 className="text-md font-medium text-[#F79B72] mb-2">Rollback Previous Deployment</h4>
              <div>
                <Label htmlFor="rollback-select" className="text-[#F79B72]">Select Deployment</Label>
                <Select 
                  value={selectedRollbackId || ''} 
                  onValueChange={setSelectedRollbackId}
                  disabled={lastDeployments.length === 0}
                >
                <Select onOpenChange={(open) => open && refetchDeployments()}></Select>
                  <SelectTrigger id="rollback-select" className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
                    <SelectValue placeholder="Select a deployment" className="text-[#2A4759]" />
                  </SelectTrigger>
                  <SelectContent>
                    {lastDeployments.map((deployment) => (
                      <SelectItem key={deployment.id} value={deployment.id}>
                        {formatDeploymentSummary(deployment)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div className="mt-2">
                <Button 
                  type="button"
                  onClick={handleRollback} 
                  className="bg-[#2A4759] text-white hover:bg-[#2A4759]/80"
                  disabled={!selectedRollbackId || rollbackMutation.isPending || fileOperationStatus === 'running' || fileOperationStatus === 'loading'}
                >
                  {rollbackMutation.isPending ? "Rolling Back..." : "Rollback Deployment"}
                </Button>
              </div>
            </div>
          </div>
          
          {/* Shell Command Section */}
          <div className="space-y-4 bg-[#EEEEEE] p-4 rounded-md">
            <h3 className="text-lg font-medium text-[#F79B72]">Shell Command</h3>
            
            <div>
              <Label htmlFor="shell-user-select" className="text-[#F79B72]">Select User</Label>
              <Select 
                value={shellSelectedUser} 
                onValueChange={(value) => {
                  setShellSelectedUser(value);
                  // Reset working directory if user home is checked
                  if (useUserHomePath) {
                    setShellWorkingDir('');
                  }
                }}
              >
                <SelectTrigger id="shell-user-select" className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
                  <SelectValue placeholder="Select a user" className="text-[#2A4759]" />
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
                className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]"
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
                className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]"
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
              className="bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
              disabled={shellCommandMutation.isPending || shellOperationStatus === 'running' || shellOperationStatus === 'loading'}
            >
              {shellCommandMutation.isPending || shellOperationStatus === 'running' || shellOperationStatus === 'loading' ? 
                "Running..." : "Run Command"}
            </Button>
          </div>
        </div>
        
        {/* Logs Section - Aligned to match respective operation sections */}
        <div className="space-y-6">
          {/* File Deployment Logs */}
          <div>
            <LogDisplay 
              logs={fileLogs} 
              height="345px"
              fixedHeight={true}
              title="File Deployment Logs"
              status={fileOperationStatus}
            />
          </div>
          
          {/* Shell Command Logs */}
          <div>
            <LogDisplay 
              logs={shellLogs} 
              height="485px"
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
