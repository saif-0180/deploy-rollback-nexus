import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useToast } from "@/hooks/use-toast";
import { formatInTimeZone } from 'date-fns-tz';
import { useAuth } from '../contexts/AuthContext';

type SystemdStatus = 'loading' | 'idle' | 'running' | 'success' | 'failed' | 'completed';

const SystemctlOperations = () => {
  const [vms, setVms] = useState<string[]>([]);
  const [services, setServices] = useState<string[]>([]);
  const [selectedVMs, setSelectedVMs] = useState<string[]>([]);
  const [selectedService, setSelectedService] = useState<string | undefined>(undefined);
  const [operation, setOperation] = useState<string>('restart');
  const [logs, setLogs] = useState<string[]>([]);
  const [status, setStatus] = useState<SystemdStatus>('idle');
  const [error, setError] = useState<string>('');
  const [user, setUser] = useState<string>('');
  const [selectedUser, setSelectedUser] = useState<string>('infadm');
  const timezone = 'America/New_York';
  const { authData } = useAuth();

  useEffect(() => {
    const fetchInventory = async () => {
      setStatus('loading');
      try {
        const response = await fetch('/api/inventory');
        if (!response.ok) {
          throw new Error('Failed to fetch inventory');
        }
        const data = await response.json();
        setVms(data.vms.map((vm: { name: string }) => vm.name) || []);
        setServices(data.systemd_services || []);
        setStatus('idle');
      } catch (error) {
        console.error("Error fetching inventory:", error);
        setError('Failed to load inventory.');
        setStatus('failed');
      }
    };

    fetchInventory();
  }, []);

  const executeSystemdOperation = async () => {
    if (!selectedVMs.length || !selectedService) {
      toast({
        title: "Validation Error",
        description: "Please select VMs and a service",
        variant: "destructive",
      });
      return;
    }

    setStatus('running');
    setLogs([]);
    setError('');

    const timestamp = formatInTimeZone(new Date(), timezone, 'HH:mm:ss');
    const initialLog = `[${timestamp}] Starting ${operation} operation for ${selectedService} on VMs: ${selectedVMs.join(', ')}`;
    setLogs([initialLog]);

    try {
      const response = await fetch('/api/systemd/operation', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          vms: selectedVMs,
          service: selectedService,
          operation: operation,
          user: selectedUser
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Operation failed');
      }

      setLogs(data.logs || []);
      setStatus(data.success ? 'success' : 'failed');
      
      toast({
        title: data.success ? "Operation Successful" : "Operation Failed", 
        description: `${operation} ${selectedService} ${data.success ? 'completed successfully' : 'failed'}`,
        variant: data.success ? "default" : "destructive",
      });

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      setError(errorMessage);
      setStatus('failed'); // Changed from 'timeout' to 'failed'
      
      const timestamp = formatInTimeZone(new Date(), timezone, 'HH:mm:ss');
      setLogs(prev => [...prev, `[${timestamp}] ERROR: ${errorMessage}`]);
      
      toast({
        title: "Operation Failed",
        description: errorMessage,
        variant: "destructive",
      });
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Systemctl Operations</CardTitle>
        <CardDescription>Start, stop, or restart systemd services on selected VMs.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="grid grid-cols-2 gap-2">
          <div>
            <Label htmlFor="vms">VMs</Label>
            <Select onValueChange={(value) => setSelectedVMs(value.split(','))}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Select VMs" />
              </SelectTrigger>
              <SelectContent>
                {vms.map((vm) => (
                  <SelectItem key={vm} value={vm}>{vm}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label htmlFor="service">Service</Label>
            <Select onValueChange={setSelectedService}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Select Service" />
              </SelectTrigger>
              <SelectContent>
                {services.map((service) => (
                  <SelectItem key={service} value={service}>{service}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <Label htmlFor="operation">Operation</Label>
            <Select onValueChange={setOperation}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Select Operation" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="start">Start</SelectItem>
                <SelectItem value="stop">Stop</SelectItem>
                <SelectItem value="restart">Restart</SelectItem>
                <SelectItem value="status">Status</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="user">User</Label>
            <Input
              id="user"
              type="text"
              value={selectedUser}
              onChange={(e) => setSelectedUser(e.target.value)}
              placeholder="Enter User"
            />
          </div>
        </div>

        <Button onClick={executeSystemdOperation} disabled={status === 'running'}>
          {status === 'running' ? 'Executing...' : 'Execute'}
        </Button>

        {error && <p className="text-red-500">Error: {error}</p>}

        <div className="relative">
          <Label htmlFor="logs">Logs</Label>
          <ScrollArea className="h-[200px] w-full rounded-md border bg-muted">
            <Textarea
              readOnly
              value={logs.join('\n')}
              className="min-h-[200px] w-full resize-none border-none bg-transparent p-4 focus-visible:outline-none focus-visible:ring-0"
            />
          </ScrollArea>
        </div>
      </CardContent>
    </Card>
  );
};

export default SystemctlOperations;
