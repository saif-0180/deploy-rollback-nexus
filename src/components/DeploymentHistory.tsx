
import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import LogDisplay from '@/components/LogDisplay';
import { Loader2, RefreshCw } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { toLocaleStringWithTimezone, getCurrentTimeInTimezone } from '@/utils/timezone';

interface Deployment {
  id: string;
  type: 'file' | 'sql' | 'systemd' | 'command' | 'rollback' | 'template' | string; 
  status: 'running' | 'success' | 'failed' | string;
  timestamp: string;
  ft?: string;
  file?: string;
  vms?: string[];
  service?: string;
  operation?: string;
  command?: string;
  logs?: string[];
  original_deployment?: string;
  logged_in_user?: string;
  template?: string;
}

interface TemplateDeployment {
  id: string;
  template: string;
  ft_number: string;
  status: 'running' | 'success' | 'failed' | string;
  timestamp: string;
  logs: string[];
  logged_in_user: string;
}

const DeploymentHistory: React.FC = () => {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [selectedDeploymentId, setSelectedDeploymentId] = useState<string | null>(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [deploymentLogs, setDeploymentLogs] = useState<string[]>([]);
  const [templateLogs, setTemplateLogs] = useState<string[]>([]);
  const [clearDays, setClearDays] = useState<number>(30);
  const [logStatus, setLogStatus] = useState<'idle' | 'loading' | 'running' | 'success' | 'failed' | 'completed'>('idle');
  const [templateLogStatus, setTemplateLogStatus] = useState<'idle' | 'loading' | 'running' | 'success' | 'failed' | 'completed'>('idle');
  const [lastRefreshedTime, setLastRefreshedTime] = useState<string>('');
  const [apiErrorMessage, setApiErrorMessage] = useState<string>("");

  // Fetch regular deployment history
  const { 
    data: deployments = [], 
    refetch: refetchDeployments, 
    isLoading: isLoadingDeployments,
    isError: isErrorDeployments
  } = useQuery({
    queryKey: ['deployment-history'],
    queryFn: async () => {
      console.log("Fetching deployment history");
      setApiErrorMessage("");
      try {
        const response = await fetch('/api/deployments/history');
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.indexOf("application/json") === -1) {
          const errorText = await response.text();
          console.error(`Server returned non-JSON response: ${errorText}`);
          setApiErrorMessage("API returned HTML instead of JSON. Backend service might be unavailable.");
          return [];
        }
        
        if (!response.ok) {
          const errorText = await response.text();
          console.error(`Failed to fetch deployment history: ${errorText}`);
          setApiErrorMessage(`Failed to fetch deployment history: ${response.status} ${response.statusText}`);
          throw new Error('Failed to fetch deployment history');
        }
        
        const data = await response.json();
        console.log("Received deployment history data:", data);
        setLastRefreshedTime(getCurrentTimeInTimezone('h:mm:ss a'));
        return data as Deployment[];
      } catch (error) {
        console.error(`Error in history fetch: ${error}`);
        if (error instanceof SyntaxError) {
          setApiErrorMessage("Server returned invalid JSON. The backend might be down or misconfigured.");
        } else {
          setApiErrorMessage(`Error fetching deployment history: ${error instanceof Error ? error.message : String(error)}`);
        }
        return [];
      }
    },
    staleTime: 300000,
    refetchInterval: 1800000,
    refetchOnWindowFocus: false,
    retry: 2,
  });

  // Fetch template deployment history
  const { 
    data: templateDeployments = [], 
    refetch: refetchTemplateDeployments, 
    isLoading: isLoadingTemplateDeployments,
    isError: isErrorTemplateDeployments
  } = useQuery({
    queryKey: ['template-deployment-history'],
    queryFn: async () => {
      console.log("Fetching template deployment history");
      try {
        const response = await fetch('/api/template-deployments/history');
        if (!response.ok) {
          console.error('Failed to fetch template deployments');
          return [];
        }
        const data = await response.json();
        console.log("Received template deployment history data:", data);
        return data as TemplateDeployment[];
      } catch (error) {
        console.error(`Error in template history fetch: ${error}`);
        return [];
      }
    },
    staleTime: 300000,
    refetchInterval: 1800000,
    refetchOnWindowFocus: false,
    retry: 2,
  });

  // Function to fetch logs for regular deployments
  const fetchDeploymentLogs = async (deploymentId: string) => {
    if (!deploymentId) return;
    
    try {
      setLogStatus('loading');
      console.log(`Fetching logs for deployment ${deploymentId}`);
      const response = await fetch(`/api/deploy/${deploymentId}/logs`);
      if (!response.ok) {
        throw new Error(`Failed to fetch logs: ${await response.text()}`);
      }
      const data = await response.json();
      console.log(`Received logs for ${deploymentId}:`, data);
      
      if (data.logs && data.logs.length > 0) {
        setDeploymentLogs(data.logs);
        setLogStatus(data.status === 'running' ? 'running' : 'completed');
      } else {
        const selectedDeployment = deployments.find(d => d.id === deploymentId);
        if (selectedDeployment?.logs && selectedDeployment.logs.length > 0) {
          setDeploymentLogs(selectedDeployment.logs);
          setLogStatus(selectedDeployment.status === 'running' ? 'running' : 'completed');
        } else {
          setDeploymentLogs([`No detailed logs available for deployment ${deploymentId}`]);
          setLogStatus('completed');
        }
      }
    } catch (error) {
      console.error('Error fetching logs:', error);
      setDeploymentLogs(["Error loading logs. Please try again."]);
      setLogStatus('failed');
    }
  };

  // Function to fetch logs for template deployments
  const fetchTemplateLogs = async (templateId: string) => {
    if (!templateId) return;
    
    try {
      setTemplateLogStatus('loading');
      console.log(`Fetching template logs for ${templateId}`);
      const response = await fetch(`/api/template-deploy/${templateId}/logs`);
      if (!response.ok) {
        throw new Error(`Failed to fetch template logs: ${await response.text()}`);
      }
      const data = await response.json();
      console.log(`Received template logs for ${templateId}:`, data);
      
      if (data.logs && data.logs.length > 0) {
        setTemplateLogs(data.logs);
        setTemplateLogStatus(data.status === 'running' ? 'running' : 'completed');
      } else {
        const selectedTemplate = templateDeployments.find(d => d.id === templateId);
        if (selectedTemplate?.logs && selectedTemplate.logs.length > 0) {
          setTemplateLogs(selectedTemplate.logs);
          setTemplateLogStatus(selectedTemplate.status === 'running' ? 'running' : 'completed');
        } else {
          setTemplateLogs([`No detailed logs available for template deployment ${templateId}`]);
          setTemplateLogStatus('completed');
        }
      }
    } catch (error) {
      console.error('Error fetching template logs:', error);
      setTemplateLogs(["Error loading template logs. Please try again."]);
      setTemplateLogStatus('failed');
    }
  };

  // Effects for loading logs
  useEffect(() => {
    if (!selectedDeploymentId) {
      setLogStatus('idle');
      return;
    }
    fetchDeploymentLogs(selectedDeploymentId);
  }, [selectedDeploymentId]);

  useEffect(() => {
    if (!selectedTemplateId) {
      setTemplateLogStatus('idle');
      return;
    }
    fetchTemplateLogs(selectedTemplateId);
  }, [selectedTemplateId]);

  // Manual refresh functions
  const handleRefresh = () => {
    refetchDeployments();
    if (selectedDeploymentId) {
      fetchDeploymentLogs(selectedDeploymentId);
    }
  };

  const handleTemplateRefresh = () => {
    refetchTemplateDeployments();
    if (selectedTemplateId) {
      fetchTemplateLogs(selectedTemplateId);
    }
  };

  // Clear logs mutation
  const clearLogsMutation = useMutation({
    mutationFn: async (days: number) => {
      const response = await fetch('/api/deployments/clear', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ days }),
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error(`Failed to clear logs: ${errorText}`);
        throw new Error('Failed to clear logs');
      }
      
      return response.json();
    },
    onSuccess: (data) => {
      toast({
        title: "Logs Cleared",
        description: data.message || "Logs have been cleared successfully",
      });
      refetchDeployments();
      refetchTemplateDeployments();
      setSelectedDeploymentId(null);
      setSelectedTemplateId(null);
      setDeploymentLogs([]);
      setTemplateLogs([]);
    },
    onError: (error) => {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to clear logs",
        variant: "destructive",
      });
    },
  });

  // Auto-select first deployment
  useEffect(() => {
    if (deployments && deployments.length > 0 && !selectedDeploymentId && !isLoadingDeployments) {
      setSelectedDeploymentId(deployments[0].id);
    }
  }, [deployments, selectedDeploymentId, isLoadingDeployments]);

  // Auto-select first template deployment
  useEffect(() => {
    if (templateDeployments && templateDeployments.length > 0 && !selectedTemplateId && !isLoadingTemplateDeployments) {
      setSelectedTemplateId(templateDeployments[0].id);
    }
  }, [templateDeployments, selectedTemplateId, isLoadingTemplateDeployments]);

  // Format deployment summary
  const formatDeploymentSummary = (deployment: Deployment): string => {
    const dateTime = deployment.timestamp ? 
      toLocaleStringWithTimezone(deployment.timestamp) :
      'Unknown date';

    const userPrefix = deployment.logged_in_user ? `User: ${deployment.logged_in_user} - ` : '';

    switch (deployment.type) {
      case 'file':
        return `${userPrefix}File: FT=${deployment.ft || 'N/A'}, File=${deployment.file || 'N/A'}, Status=${deployment.status}, ${dateTime}`;
      case 'sql':
        return `${userPrefix}SQL: ${deployment.ft || 'N/A'}/${deployment.file || 'N/A'}, Status=${deployment.status}, ${dateTime}`;
      case 'systemd':
        return `${userPrefix}Systemctl: ${deployment.operation || 'N/A'} ${deployment.service || 'N/A'}, Status=${deployment.status}, ${dateTime}`;
      case 'command':
        return `${userPrefix}Command: ${deployment.command ? `${deployment.command.substring(0, 30)}${deployment.command.length > 30 ? '...' : ''}` : 'N/A'}, Status=${deployment.status}, ${dateTime}`;
      case 'rollback':
        return `${userPrefix}Rollback: ${deployment.ft || 'N/A'}/${deployment.file || 'N/A'}, Status=${deployment.status}, ${dateTime}`;
      case 'template':
        return `${userPrefix}Template: ${deployment.template || 'N/A'}, Status=${deployment.status}, ${dateTime}`;
      default:
        return `${userPrefix}${deployment.type} (${deployment.status}), ${dateTime}`;
    }
  };

  // Format template deployment summary
  const formatTemplateDeploymentSummary = (deployment: TemplateDeployment): string => {
    const dateTime = deployment.timestamp ? 
      toLocaleStringWithTimezone(deployment.timestamp) :
      'Unknown date';

    const userPrefix = deployment.logged_in_user ? `User: ${deployment.logged_in_user} - ` : '';
    
    return `${userPrefix}Template: ${deployment.template}, FT: ${deployment.ft_number}, Status=${deployment.status}, ${dateTime}`;
  };

  const handleClearLogs = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (clearDays < 0) {
      toast({
        title: "Invalid Input",
        description: "Days must be a positive number or zero to clear all",
        variant: "destructive",
      });
      return;
    }
    
    clearLogsMutation.mutate(clearDays);
  };

  // Get selected deployment details
  const getSelectedDeployment = (): Deployment | undefined => {
    if (!selectedDeploymentId || !deployments) return undefined;
    return deployments.find(d => d.id === selectedDeploymentId);
  };

  // Get selected template deployment details
  const getSelectedTemplateDeployment = (): TemplateDeployment | undefined => {
    if (!selectedTemplateId || !templateDeployments) return undefined;
    return templateDeployments.find(d => d.id === selectedTemplateId);
  };

  // Get deployment summary for logs title
  const getDeploymentSummary = (): string => {
    const deployment = getSelectedDeployment();
    if (!deployment) return "Select a deployment to view details";
    
    const userInfo = deployment.logged_in_user ? `User: ${deployment.logged_in_user} - ` : '';
    const typeInfo = deployment.type === 'rollback' ? 
      `Rollback: ${deployment.ft || 'N/A'}/${deployment.file || 'N/A'}` :
      deployment.type === 'file' ?
      `File: FT=${deployment.ft || 'N/A'}, File=${deployment.file || 'N/A'}` :
      deployment.type === 'systemd' ?
      `Systemctl: ${deployment.operation || 'N/A'} ${deployment.service || 'N/A'}` :
      deployment.type === 'template' ?
      `Template: ${deployment.template || 'N/A'}` :
      deployment.type;
    
    const statusInfo = `Status=${deployment.status}`;
    const dateTime = deployment.timestamp ? 
      toLocaleStringWithTimezone(deployment.timestamp) : 
      'Unknown date';
    
    return `${userInfo}${typeInfo}, ${statusInfo}, ${dateTime}`;
  };

  // Get template deployment summary for logs title
  const getTemplateDeploymentSummary = (): string => {
    const deployment = getSelectedTemplateDeployment();
    if (!deployment) return "Select a template deployment to view details";
    
    const userInfo = deployment.logged_in_user ? `User: ${deployment.logged_in_user} - ` : '';
    const statusInfo = `Status=${deployment.status}`;
    const dateTime = deployment.timestamp ? 
      toLocaleStringWithTimezone(deployment.timestamp) : 
      'Unknown date';
    
    return `${userInfo}Template: ${deployment.template}, FT: ${deployment.ft_number}, ${statusInfo}, ${dateTime}`;
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-[#F79B72] mb-4">Deployment History</h2>
      
      <Tabs defaultValue="all-logs" className="w-full">
        <TabsList className="grid w-full grid-cols-2 bg-[#2A4759] mb-6">
          <TabsTrigger value="all-logs" className="data-[state=active]:bg-[#F79B72] data-[state=active]:text-[#2A4759] text-[#EEEEEE]">
            All Logs
          </TabsTrigger>
          <TabsTrigger value="template-logs" className="data-[state=active]:bg-[#F79B72] data-[state=active]:text-[#2A4759] text-[#EEEEEE]">
            Template Logs
          </TabsTrigger>
        </TabsList>

        <TabsContent value="all-logs">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Regular Deployment List */}
            <div className="space-y-4">
              <Card className="bg-[#EEEEEE]">
                <CardHeader className="pb-2">
                  <div className="flex justify-between items-center">
                    <div>
                      <CardTitle className="text-[#F79B72] text-lg">Recent Deployments</CardTitle>
                      <p className="text-xs text-gray-500 mt-1">Last refreshed: {lastRefreshedTime}</p>
                    </div>
                    <Button
                      type="button"
                      onClick={handleRefresh}
                      className="bg-[#2A4759] text-white hover:bg-[#2A4759]/80 h-8 w-8 p-0"
                      title="Refresh"
                      disabled={isLoadingDeployments}
                    >
                      {isLoadingDeployments ? 
                        <Loader2 className="h-4 w-4 animate-spin" /> : 
                        <RefreshCw className="h-4 w-4" />
                      }
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="h-[400px] overflow-y-auto">
                    {isLoadingDeployments ? (
                      <div className="flex items-center justify-center h-full">
                        <Loader2 className="h-8 w-8 animate-spin text-[#F79B72]" />
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {apiErrorMessage && (
                          <div className="p-4 bg-red-100 text-red-800 rounded-md mb-4">
                            <p className="font-medium">API Error:</p>
                            <p className="text-sm">{apiErrorMessage}</p>
                          </div>
                        )}
                        
                        {deployments.length === 0 ? (
                          <p className="text-[#2A4759] italic">
                            {apiErrorMessage ? "Could not load deployment history" : "No deployment history found"}
                          </p>
                        ) : (
                          deployments.map((deployment) => (
                            <div 
                              key={deployment.id} 
                              className={`p-3 rounded-md cursor-pointer transition-colors ${
                                selectedDeploymentId === deployment.id 
                                  ? 'bg-[#F79B72] text-[#2A4759]' 
                                  : 'bg-[#2A4759] text-[#EEEEEE] hover:bg-[#2A4759]/80'
                              }`}
                              onClick={() => setSelectedDeploymentId(deployment.id)}
                            >
                              <div className="flex justify-between">
                                <div>
                                  {formatDeploymentSummary(deployment)}
                                </div>
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                    )}
                  </div>
                  
                  <form onSubmit={handleClearLogs} className="mt-4 flex items-center space-x-2">
                    <Label htmlFor="clear-days" className="text-[#F79B72]">Days to keep:</Label>
                    <Input 
                      id="clear-days" 
                      type="number" 
                      value={clearDays} 
                      onChange={(e) => setClearDays(parseInt(e.target.value) || 0)}
                      className="w-20 bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]"
                    />
                    <Button 
                      type="submit"
                      disabled={clearLogsMutation.isPending}
                      className="bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
                    >
                      {clearLogsMutation.isPending ? "Clearing..." : "Clear Logs"}
                    </Button>
                  </form>
                </CardContent>
              </Card>
            </div>
            
            {/* Regular Deployment Details */}
            <div className="space-y-4">
              <LogDisplay 
                logs={deploymentLogs} 
                height="400px" 
                title={`Deployment Details - ${getDeploymentSummary()}`}
                status={logStatus as "idle" | "loading" | "running" | "success" | "failed" | "completed"}
              />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="template-logs">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Template Deployment List */}
            <div className="space-y-4">
              <Card className="bg-[#EEEEEE]">
                <CardHeader className="pb-2">
                  <div className="flex justify-between items-center">
                    <div>
                      <CardTitle className="text-[#F79B72] text-lg">Template Deployments</CardTitle>
                      <p className="text-xs text-gray-500 mt-1">Last refreshed: {lastRefreshedTime}</p>
                    </div>
                    <Button
                      type="button"
                      onClick={handleTemplateRefresh}
                      className="bg-[#2A4759] text-white hover:bg-[#2A4759]/80 h-8 w-8 p-0"
                      title="Refresh"
                      disabled={isLoadingTemplateDeployments}
                    >
                      {isLoadingTemplateDeployments ? 
                        <Loader2 className="h-4 w-4 animate-spin" /> : 
                        <RefreshCw className="h-4 w-4" />
                      }
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="h-[400px] overflow-y-auto">
                    {isLoadingTemplateDeployments ? (
                      <div className="flex items-center justify-center h-full">
                        <Loader2 className="h-8 w-8 animate-spin text-[#F79B72]" />
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {templateDeployments.length === 0 ? (
                          <p className="text-[#2A4759] italic">No template deployment history found</p>
                        ) : (
                          templateDeployments.map((deployment) => (
                            <div 
                              key={deployment.id} 
                              className={`p-3 rounded-md cursor-pointer transition-colors ${
                                selectedTemplateId === deployment.id 
                                  ? 'bg-[#F79B72] text-[#2A4759]' 
                                  : 'bg-[#2A4759] text-[#EEEEEE] hover:bg-[#2A4759]/80'
                              }`}
                              onClick={() => setSelectedTemplateId(deployment.id)}
                            >
                              <div className="flex justify-between">
                                <div>
                                  {formatTemplateDeploymentSummary(deployment)}
                                </div>
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>
            
            {/* Template Deployment Details */}
            <div className="space-y-4">
              <LogDisplay 
                logs={templateLogs} 
                height="400px" 
                title={`Template Deployment Details - ${getTemplateDeploymentSummary()}`}
                status={templateLogStatus as "idle" | "loading" | "running" | "success" | "failed" | "completed"}
              />
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default DeploymentHistory;
