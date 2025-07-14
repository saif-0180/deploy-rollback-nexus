import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { RefreshCw, Play, Loader2 } from 'lucide-react';
import VMSelector from '@/components/VMSelector';
import LogDisplay from '@/components/LogDisplay';

const SystemctlOperations: React.FC = () => {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [selectedVMs, setSelectedVMs] = useState<string[]>([]);
  const [selectedService, setSelectedService] = useState<string>('');
  const [selectedOperation, setSelectedOperation] = useState<string>('');
  const [logs, setLogs] = useState<string[]>([]);
  const [logStatus, setLogStatus] = useState<'idle' | 'loading' | 'running' | 'success' | 'failed' | 'completed'>('idle');
  const [currentDeploymentId, setCurrentDeploymentId] = useState<string | null>(null);

  // Fetch available VMs
  const { data: vms = [], refetch: refetchVMs, isLoading: isLoadingVMs } = useQuery({
    queryKey: ['vms'],
    queryFn: async () => {
      const response = await fetch('/api/inventory/vms');
      if (!response.ok) {
        throw new Error('Failed to fetch VMs');
      }
      const data = await response.json();
      return data.vms as string[];
    },
    staleTime: 300000,
    refetchOnWindowFocus: false,
  });

  // Fetch available services
  const { data: services = [], refetch: refetchServices, isLoading: isLoadingServices } = useQuery({
    queryKey: ['systemd-services'],
    queryFn: async () => {
      const response = await fetch('/api/inventory/systemd-services');
      if (!response.ok) {
        throw new Error('Failed to fetch services');
      }
      const data = await response.json();
      return data.services as string[];
    },
    staleTime: 300000,
    refetchOnWindowFocus: false,
  });

  // Mutation to execute systemctl command
  const systemctlMutation = useMutation({
    mutationFn: async ({ vms, service, operation }: { vms: string[], service: string, operation: string }) => {
      const response = await fetch('/api/systemctl/execute', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ vms, service, operation }),
      });
      if (!response.ok) {
        throw new Error('Failed to execute systemctl command');
      }
      const data = await response.json();
      return data;
    },
    onSuccess: (data) => {
      setCurrentDeploymentId(data.deployment_id);
      setLogStatus('running');
      setLogs([]);
      toast({
        title: "Command Executed",
        description: `Systemctl command executed with ID: ${data.deployment_id}`,
      });
      // Start polling for logs
      pollForLogs(data.deployment_id);
    },
    onError: (error) => {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to execute systemctl command",
        variant: "destructive",
      });
    },
  });

  // Function to poll for logs
  const pollForLogs = async (deploymentId: string) => {
    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`/api/deploy/${deploymentId}/logs`);
        if (!response.ok) {
          clearInterval(pollInterval);
          return;
        }
        
        const data = await response.json();
        setLogs(data.logs || []);
        
        if (data.status === 'success' || data.status === 'failed') {
          setLogStatus(data.status);
          clearInterval(pollInterval);
          // Refresh deployment history
          queryClient.invalidateQueries({ queryKey: ['deployment-history'] });
        }
      } catch (error) {
        console.error('Error polling logs:', error);
        clearInterval(pollInterval);
        setLogStatus('failed');
      }
    }, 2000);

    // Clean up interval after 10 minutes
    setTimeout(() => {
      clearInterval(pollInterval);
      if (logStatus === 'running') {
        setLogStatus('completed');
      }
    }, 600000);
  };

  const handleExecute = () => {
    if (selectedVMs.length > 0 && selectedService && selectedOperation) {
      systemctlMutation.mutate({ vms: selectedVMs, service: selectedService, operation: selectedOperation });
    } else {
      toast({
        title: "Error",
        description: "Please select VMs, a service, and an operation.",
        variant: "destructive",
      });
    }
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-[#F79B72] mb-4">Systemctl Operations</h2>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <Card className="bg-[#EEEEEE]">
            <CardHeader>
              <CardTitle className="text-[#F79B72] text-lg">Service Management</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <VMSelector onVMChange={setSelectedVMs} />
              
              <div className="flex items-center space-x-2">
                <Select value={selectedService} onValueChange={setSelectedService}>
                  <SelectTrigger className="flex-1 bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
                    <SelectValue placeholder="Select a service" />
                  </SelectTrigger>
                  <SelectContent>
                    {services.map((service) => (
                      <SelectItem key={service} value={service}>
                        {service}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  type="button"
                  onClick={() => refetchServices()}
                  className="bg-[#2A4759] text-white hover:bg-[#2A4759]/80 h-10 w-10 p-0"
                  title="Refresh Services"
                  disabled={isLoadingServices}
                >
                  {isLoadingServices ? 
                    <Loader2 className="h-4 w-4 animate-spin" /> : 
                    <RefreshCw className="h-4 w-4" />
                  }
                </Button>
              </div>

              <Select value={selectedOperation} onValueChange={setSelectedOperation}>
                <SelectTrigger className="w-full bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
                  <SelectValue placeholder="Select an operation" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="start">Start</SelectItem>
                  <SelectItem value="stop">Stop</SelectItem>
                  <SelectItem value="restart">Restart</SelectItem>
                  <SelectItem value="status">Status</SelectItem>
                </SelectContent>
              </Select>
              
              <Button
                onClick={handleExecute}
                disabled={systemctlMutation.isLoading || logStatus === 'running'}
                className="bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
              >
                {systemctlMutation.isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Executing...
                  </>
                ) : (
                  <>
                    <Play className="mr-2 h-4 w-4" />
                    Execute
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <LogDisplay 
            logs={logs} 
            height="400px" 
            title={`Systemctl Logs${currentDeploymentId ? ` - ${currentDeploymentId}` : ''}`}
            status={logStatus}
          />
        </div>
      </div>
    </div>
  );
};

export default SystemctlOperations;
