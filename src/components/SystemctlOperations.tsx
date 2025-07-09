import React, { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { useToast } from "@/hooks/use-toast";
import { useMutation } from '@tanstack/react-query';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import LogDisplay from '@/components/LogDisplay';
import VMSelector from '@/components/VMSelector';
import { useAuth } from '@/contexts/AuthContext';

const SystemctlOperations: React.FC = () => {
  const { toast } = useToast();
  const { user } = useAuth();
  const [selectedService, setSelectedService] = useState<string>("");
  const [selectedOperation, setSelectedOperation] = useState<string>("");
  const [selectedVMs, setSelectedVMs] = useState<string[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [deploymentId, setDeploymentId] = useState<string | null>(null);
  const [useSudo, setUseSudo] = useState<boolean>(false);
  const [operationStatus, setOperationStatus] = useState<'idle' | 'loading' | 'running' | 'success' | 'failed' | 'completed'>('idle');

  const systemctlMutation = useMutation({
    mutationFn: async () => {
      setOperationStatus('loading');
      const response = await fetch('/api/systemctl/operation', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          service: selectedService,
          operation: selectedOperation,
          vms: selectedVMs,
          sudo: useSudo
        }),
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Failed to execute systemctl operation');
      }
      
      const data = await response.json();
      setDeploymentId(data.deploymentId);
      setOperationStatus('running');
      return data;
    },
    onSuccess: (data) => {
      toast({
        title: "Operation Started",
        description: `Systemctl ${selectedOperation} operation initiated for ${selectedService}`,
      });
      startPollingLogs(data.deploymentId);
    },
    onError: (error) => {
      setOperationStatus('failed');
      toast({
        title: "Operation Failed",
        description: error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
      });
    },
  });

  // Add a function to poll for logs with improved completion detection
  const startPollingLogs = (id: string) => {
    if (!id) return;
    
    // Start with a clear log display
    setLogs([]);
    setOperationStatus('running');
    
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
          setLogs(data.logs);
          
          // Check if operation is explicitly complete
          if (data.status === 'completed' || data.status === 'success') {
            setOperationStatus('success');
            clearInterval(pollInterval);
            return;
          }
          
          if (data.status === 'failed') {
            setOperationStatus('failed');
            clearInterval(pollInterval);
            return;
          }
          
          // Check for implicit completion (logs not changing)
          if (data.logs.length === lastLogLength) {
            pollCount++;
            if (pollCount >= 5) { // After 5 consecutive polls with no changes
              console.log('Operation appears complete - logs have not changed');
              setOperationStatus('completed');
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
          setOperationStatus(data.status === 'running' ? 'running' : 'completed');
          clearInterval(pollInterval);
        }
      } catch (error) {
        console.error('Error fetching logs:', error);
        // Don't clear interval yet, try a few more times
        pollCount += 5;
        if (pollCount > 20) {  // After several failures, give up
          setOperationStatus('failed');
          clearInterval(pollInterval);
        }
      }
    }, 1000); // Poll every second
    
    // Clean up on unmount
    return () => {
      clearInterval(pollInterval);
    };
  };

  // Fetch log updates if deploymentId is set
  useEffect(() => {
    if (deploymentId) {
      return startPollingLogs(deploymentId);
    }
  }, [deploymentId]);

  const handleExecute = (e: React.MouseEvent) => {
    e.preventDefault();
    
    if (!selectedService || !selectedOperation) {
      toast({
        title: "Validation Error",
        description: "Please select both service and operation.",
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

    setLogs([]);
    systemctlMutation.mutate();
  };

  const handleVMSelectionChange = (vms: string[]) => {
    setSelectedVMs(vms);
  };

  const services = [
    "docker.service",
    "nginx.service",
    "postgresql.service",
    "redis.service",
    "ssh.service",
    "firewalld.service",
    "NetworkManager.service",
    "chronyd.service",
    "rsyslog.service",
    "systemd-journald.service"
  ];

  const operations = [
    { value: "start", label: "Start" },
    { value: "stop", label: "Stop" },
    { value: "restart", label: "Restart" },
    { value: "status", label: "Status" },
    { value: "enable", label: "Enable" },
    { value: "disable", label: "Disable" },
    { value: "reload", label: "Reload" }
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-[#F79B72] mb-4">Systemctl Operations</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-4 bg-[#EEEEEE] p-4 rounded-md">
          <div>
            <Label htmlFor="service-select" className="text-[#F79B72]">Select Service</Label>
            <Select value={selectedService} onValueChange={setSelectedService}>
              <SelectTrigger id="service-select" className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
                <SelectValue placeholder="Select a service" className="text-[#2A4759]" />
              </SelectTrigger>
              <SelectContent className="bg-[#DDDDDD] border-[#2A4759] text-[#2A4759]">
                {services.map((service: string) => (
                  <SelectItem key={service} value={service} className="text-[#2A4759]">{service}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label htmlFor="operation-select" className="text-[#F79B72]">Select Operation</Label>
            <Select value={selectedOperation} onValueChange={setSelectedOperation}>
              <SelectTrigger id="operation-select" className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
                <SelectValue placeholder="Select an operation" className="text-[#2A4759]" />
              </SelectTrigger>
              <SelectContent className="bg-[#DDDDDD] border-[#2A4759] text-[#2A4759]">
                {operations.map((op) => (
                  <SelectItem key={op.value} value={op.value} className="text-[#2A4759]">{op.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label className="text-[#F79B72]">Select VMs</Label>
            <VMSelector 
              onSelectionChange={handleVMSelectionChange}
              selectedVMs={selectedVMs}
            />
          </div>

          <div className="flex items-center space-x-2">
            <Checkbox 
              id="use-sudo" 
              checked={useSudo} 
              onCheckedChange={(checked) => setUseSudo(checked as boolean)}
            />
            <Label htmlFor="use-sudo" className="text-[#2A4759]">Use sudo</Label>
          </div>

          <Button 
            type="button"
            onClick={handleExecute}
            className="bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
            disabled={systemctlMutation.isPending || operationStatus === 'running' || operationStatus === 'loading'}
          >
            {systemctlMutation.isPending || operationStatus === 'running' || operationStatus === 'loading' ? "Executing..." : "Execute Operation"}
          </Button>
        </div>

        <div>
          <LogDisplay 
            logs={logs} 
            height="400px" 
            fixedHeight={true} 
            title={`Systemctl Logs${user?.username ? ` - User: ${user.username}` : ''}`}
            status={operationStatus}
          />
        </div>
      </div>
    </div>
  );
};

export default SystemctlOperations;
