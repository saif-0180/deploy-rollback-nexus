import React, { useState, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import VMSelector from '@/components/VMSelector';
import LogDisplay from '@/components/LogDisplay';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

const SystemctlOperations: React.FC = () => {
  const { toast } = useToast();
  const { user } = useAuth();
  const [selectedVMs, setSelectedVMs] = useState<string[]>([]);
  const [service, setService] = useState<string>('');
  const [operation, setOperation] = useState<string>('restart');
  const [logs, setLogs] = useState<string[]>([]);
  const [logStatus, setLogStatus] = useState<'idle' | 'loading' | 'running' | 'success' | 'failed' | 'completed'>('idle');

  const systemctlMutation = useMutation({
    mutationFn: async () => {
      setLogStatus('loading');
      setLogs([]);
      
      const response = await fetch('/api/systemctl', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          vms: selectedVMs,
          service: service,
          operation: operation,
        }),
      });

      if (!response.ok) {
        setLogStatus('failed');
        const errorText = await response.text();
        console.error(`Systemctl operation failed: ${errorText}`);
        throw new Error(`Systemctl operation failed: ${errorText}`);
      }

      const data = await response.json();
      
      if (data.logs && data.logs.length > 0) {
        setLogs(data.logs);
        setLogStatus(data.status === 'running' ? 'running' : 'completed');
      } else {
        setLogs([`No detailed logs available for ${operation} ${service}`]);
        setLogStatus('completed');
      }
      
      return data;
    },
    onSuccess: () => {
      toast({
        title: "Systemctl Operation",
        description: `Successfully executed ${operation} on ${service}`,
      });
    },
    onError: (error) => {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to execute systemctl operation",
        variant: "destructive",
      });
    },
  });

  const handleSystemctl = async () => {
    if (!service) {
      toast({
        title: "Missing Service Name",
        description: "Please enter a service name.",
        variant: "destructive",
      });
      return;
    }

    if (selectedVMs.length === 0) {
      toast({
        title: "No VMs Selected",
        description: "Please select at least one VM.",
        variant: "destructive",
      });
      return;
    }

    systemctlMutation.mutate();
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-[#F79B72] mb-4">Systemctl Operations</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card className="bg-[#EEEEEE]">
          <CardHeader>
            <CardTitle className="text-[#F79B72]">Service Control</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="service" className="text-[#F79B72]">Service Name</Label>
              <Input
                id="service"
                type="text"
                value={service}
                onChange={(e) => setService(e.target.value)}
                placeholder="e.g., docker, nginx, apache2"
                className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="operation" className="text-[#F79B72]">Operation</Label>
              <Select value={operation} onValueChange={setOperation}>
                <SelectTrigger className="bg-[#EEEEEE] border-[#2A4759] text-[#2A4759]">
                  <SelectValue placeholder="Select operation" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="start">Start</SelectItem>
                  <SelectItem value="stop">Stop</SelectItem>
                  <SelectItem value="restart">Restart</SelectItem>
                  <SelectItem value="reload">Reload</SelectItem>
                  <SelectItem value="enable">Enable</SelectItem>
                  <SelectItem value="disable">Disable</SelectItem>
                  <SelectItem value="status">Status</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <VMSelector onVMChange={setSelectedVMs} />

            <Button 
              onClick={handleSystemctl}
              disabled={systemctlMutation.isPending || !service || selectedVMs.length === 0}
              className="w-full bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
            >
              {systemctlMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Executing...
                </>
              ) : (
                `Execute ${operation}`
              )}
            </Button>
          </CardContent>
        </Card>

        <LogDisplay 
          logs={logs} 
          height="400px" 
          title="Service Control Logs"
          status={logStatus}
        />
      </div>
    </div>
  );
};

export default SystemctlOperations;
