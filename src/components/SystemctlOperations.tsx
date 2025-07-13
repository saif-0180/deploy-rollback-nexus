import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useMutation } from "@tanstack/react-query";
import { useAuth } from '@/contexts/AuthContext';
import VMSelector from './VMSelector';
import LogDisplay from './LogDisplay';

const SystemctlOperations: React.FC = () => {
  const [selectedVMs, setSelectedVMs] = useState<string[]>([]);
  const [service, setService] = useState('');
  const [operation, setOperation] = useState('');
  const [logs, setLogs] = useState<string[]>([]);
  const [logStatus, setLogStatus] = useState<'idle' | 'loading' | 'running' | 'success' | 'completed' | 'failed'>('idle');
  const [deploymentId, setDeploymentId] = useState<string | null>(null);
  const { toast } = useToast();
  const { user } = useAuth();

  useEffect(() => {
    if (!deploymentId) return;

    const pollLogs = async () => {
      setLogStatus('loading');
      try {
        console.log(`📥 Polling logs for deployment: ${deploymentId}`);
        const response = await fetch(`/api/deploy/${deploymentId}/logs`);
        if (!response.ok) {
          console.error(`❌ Failed to fetch logs: ${response.status}`);
          setLogStatus('failed');
          return;
        }

        const data = await response.json();
        console.log(`✅ Logs received:`, data);

        if (data.logs && Array.isArray(data.logs)) {
          setLogs(data.logs);
        }

        if (data.status) {
          const status = data.status;
          console.log(`📊 Deployment status: ${status}`);

          if (status === 'success') {
            setLogStatus('completed');
          } else if (status === 'failed') {
            setLogStatus('failed');
          } else if (status === 'running') {
            setLogStatus('running');
          }
        }
      } catch (error) {
        console.error('❌ Error polling logs:', error);
        setLogStatus('failed');
      }
    };

    // Poll every 2 seconds
    const intervalId = setInterval(pollLogs, 2000);

    // Clean up interval on unmount
    return () => clearInterval(intervalId);
  }, [deploymentId]);

  const systemctlMutation = useMutation({
    mutationFn: async (data: { vms: string[], service: string, operation: string }) => {
      console.log("🔧 Starting systemctl operation:", data);
      const response = await fetch('/api/deploy/systemd', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });

      console.log("📡 Systemctl response status:", response.status);
      if (!response.ok) {
        const errorText = await response.text();
        console.error("❌ Systemctl operation failed:", errorText);
        throw new Error('Failed to execute systemctl operation');
      }

      const result = await response.json();
      console.log("✅ Systemctl operation result:", result);
      return result;
    },
    onSuccess: (data) => {
      setDeploymentId(data.deploymentId);
      setLogStatus('running');
      console.log("✅ Systemctl operation started with ID:", data.deploymentId);
      toast({
        title: "Operation Started",
        description: `Systemctl operation initiated with ID: ${data.deploymentId}`,
      });
    },
    onError: (error) => {
      console.error("❌ Systemctl operation error:", error);
      setLogStatus('failed');
      toast({
        title: "Operation Failed",
        description: `Failed to start systemctl operation: ${error instanceof Error ? error.message : 'Unknown error'}`,
        variant: "destructive",
      });
    },
  });

  const handleSystemctlOperation = () => {
    if (!selectedVMs.length) {
      toast({
        title: "Error",
        description: "Please select at least one VM",
        variant: "destructive",
      });
      return;
    }

    if (!service) {
      toast({
        title: "Error",
        description: "Please enter a service name",
        variant: "destructive",
      });
      return;
    }

    if (!operation) {
      toast({
        title: "Error",
        description: "Please select an operation",
        variant: "destructive",
      });
      return;
    }

    console.log("🔧 Handle systemctl operation:", { selectedVMs, service, operation });
    setLogs([]);
    systemctlMutation.mutate({
      vms: selectedVMs,
      service,
      operation
    });
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-[#F79B72] mb-4">Systemctl Operations</h2>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="bg-[#1a2b42] text-[#EEEEEE] border-2 border-[#EEEEEE]/30">
          <CardHeader>
            <CardTitle className="text-[#F79B72]">Service Management</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <VMSelector onVMsChange={setSelectedVMs} />
            
            <div>
              <Label htmlFor="service" className="text-[#F79B72]">Service Name</Label>
              <input
                id="service"
                type="text"
                placeholder="e.g., docker, nginx, apache2"
                value={service}
                onChange={(e) => setService(e.target.value)}
                className="w-full mt-1 px-3 py-2 bg-[#2A4759] text-[#EEEEEE] border border-[#EEEEEE]/30 rounded-md focus:outline-none focus:ring-2 focus:ring-[#F79B72]"
              />
            </div>

            <div>
              <Label htmlFor="operation" className="text-[#F79B72]">Operation</Label>
              <Select value={operation} onValueChange={setOperation}>
                <SelectTrigger className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
                  <SelectValue placeholder="Select operation" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="start">Start</SelectItem>
                  <SelectItem value="stop">Stop</SelectItem>
                  <SelectItem value="restart">Restart</SelectItem>
                  <SelectItem value="status">Status</SelectItem>
                  <SelectItem value="enable">Enable</SelectItem>
                  <SelectItem value="disable">Disable</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <Button
              onClick={handleSystemctlOperation}
              disabled={systemctlMutation.isPending || logStatus === 'running'}
              className="w-full bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
            >
              {systemctlMutation.isPending || logStatus === 'running' ? "Executing..." : "Execute"}
            </Button>

            {deploymentId && (
              <div className="mt-4 p-3 bg-[#2A4759]/50 rounded-md">
                <h4 className="text-[#F79B72] font-medium mb-2">Operation Status</h4>
                <div className="text-sm text-[#EEEEEE] space-y-1">
                  <div>ID: {deploymentId}</div>
                  <div>Status: <span className={`capitalize ${
                    logStatus === 'completed' || logStatus === 'success' ? 'text-green-400' : 
                    logStatus === 'failed' ? 'text-red-400' :
                    logStatus === 'running' ? 'text-yellow-400' : 'text-gray-400'
                  }`}>{logStatus}</span></div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <LogDisplay 
          logs={logs} 
          height="500px" 
          title="Systemctl Operation Logs"
          status={logStatus}
        />
      </div>
    </div>
  );
};

export default SystemctlOperations;
