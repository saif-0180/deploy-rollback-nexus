import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { Label } from "@/components/ui/label";
import LogDisplay from '@/components/LogDisplay';
import { Loader2, RefreshCw } from 'lucide-react';
import VMSelector from '@/components/VMSelector';
import { DeploymentStatus } from '@/components/ui/types';

interface SystemctlOperation {
  service: string;
  operation: 'start' | 'stop' | 'restart';
  vms: string[];
}

const serviceOptions = [
  "docker",
  "nginx",
  "postgresql",
  "redis",
  "other"
];

const initialOperation: SystemctlOperation = {
  service: '',
  operation: 'restart',
  vms: [],
};

const SystemctlOperations: React.FC = () => {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [operation, setOperation] = useState<SystemctlOperation>(initialOperation);
  const [logs, setLogs] = useState<string[]>([]);
  const [logStatus, setLogStatus] = useState<DeploymentStatus>('idle');
  const [lastRefreshedTime, setLastRefreshedTime] = useState<string>(new Date().toLocaleTimeString());
  const [selectedVMs, setSelectedVMs] = useState<string[]>([]);

  const handleVMSelection = (vms: string[]) => {
    setSelectedVMs(vms);
    setOperation(prev => ({ ...prev, vms: vms }));
  };

  const handleServiceChange = (service: string) => {
    setOperation(prev => ({ ...prev, service: service }));
  };

  const handleOperationChange = (operation: 'start' | 'stop' | 'restart') => {
    setOperation(prev => ({ ...prev, operation: operation }));
  };

  const systemctlMutation = useMutation({
    mutationFn: async (operation: SystemctlOperation) => {
      setLogStatus('loading');
      const response = await fetch('/api/systemctl/operate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(operation),
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error(`Failed to perform operation: ${errorText}`);
        setLogStatus('failed');
        throw new Error('Failed to perform operation');
      }
      
      const data = await response.json();
      return data;
    },
    onSuccess: (data) => {
      setLogs(data.logs || []);
      setLogStatus('success');
      toast({
        title: "Operation Successful",
        description: data.message || "Service operation completed successfully",
      });
      setLastRefreshedTime(new Date().toLocaleTimeString());
      queryClient.invalidateQueries({ queryKey: ['deployment-history'] });
    },
    onError: (error) => {
      setLogStatus('failed');
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to perform service operation",
        variant: "destructive",
      });
    },
  });

  const handleRefresh = () => {
    setLastRefreshedTime(new Date().toLocaleTimeString());
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!operation.service || operation.service === '') {
      toast({
        title: "Missing Service",
        description: "Please select a service to operate on",
        variant: "destructive",
      });
      return;
    }
    
    if (!operation.vms || operation.vms.length === 0) {
      toast({
        title: "Missing VMs",
        description: "Please select at least one VM to operate on",
        variant: "destructive",
      });
      return;
    }
    
    systemctlMutation.mutate(operation);
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-[#F79B72] mb-4">Systemctl Operations</h2>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="bg-[#EEEEEE]">
          <CardHeader>
            <CardTitle className="text-[#F79B72]">Service Management</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <Label htmlFor="service" className="text-[#F79B72]">Service</Label>
                <Select onValueChange={handleServiceChange}>
                  <SelectTrigger className="w-full bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
                    <SelectValue placeholder="Select a service" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#EEEEEE] text-[#2A4759]">
                    {serviceOptions.map((service) => (
                      <SelectItem key={service} value={service}>{service}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div>
                <Label htmlFor="operation" className="text-[#F79B72]">Operation</Label>
                <Select onValueChange={(value) => handleOperationChange(value as 'start' | 'stop' | 'restart')}>
                  <SelectTrigger className="w-full bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
                    <SelectValue placeholder="Select an operation" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#EEEEEE] text-[#2A4759]">
                    <SelectItem value="start">Start</SelectItem>
                    <SelectItem value="stop">Stop</SelectItem>
                    <SelectItem value="restart">Restart</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label className="text-[#F79B72]">Target VMs</Label>
                <VMSelector onVMsChange={handleVMSelection} />
              </div>
              
              <Button 
                type="submit"
                disabled={systemctlMutation.isPending}
                className="bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
              >
                {systemctlMutation.isPending ? "Submitting..." : "Submit"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <LogDisplay 
          logs={logs} 
          height="400px" 
          title="Systemctl Operation Logs"
          status={logStatus}
        />
      </div>
    </div>
  );
};

export default SystemctlOperations;
