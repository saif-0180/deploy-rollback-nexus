import React, { useState, useRef } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import VMSelector from './VMSelector';
import LogDisplay from './LogDisplay';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/contexts/AuthContext';

const SystemctlOperations = () => {
  const { toast } = useToast();
  const [selectedVMs, setSelectedVMs] = useState<string[]>([]);
  const [selectedService, setSelectedService] = useState<string>('');
  const [operation, setOperation] = useState<string>('status');
  const [logs, setLogs] = useState<string[]>([]);
  const [deploymentId, setDeploymentId] = useState<string | null>(null);
  const [status, setStatus] = useState<'idle' | 'loading' | 'running' | 'success' | 'failed' | 'timeout'>('idle');
  const { user } = useAuth();
  
  // Use ref to store cleanup function
  const pollCleanupRef = useRef<(() => void) | null>(null);

  // Fetch systemd services
  const { data: services = [], isLoading: isLoadingServices } = useQuery({
    queryKey: ['systemd-services'],
    queryFn: async () => {
      const response = await fetch('/api/systemd/services');
      if (!response.ok) {
        throw new Error('Failed to fetch systemd services');
      }
      return response.json();
    },
    refetchOnWindowFocus: false,
  });

  // Function to format log messages properly
  const formatLogMessage = (log: string) => {
    // Handle template variables
    if (log.includes('{ service_name }') || log.includes('{ \'running\' if service_status')) {
      return `Service ${selectedService} status check completed.`;
    }
    
    // Remove ansible-specific output that doesn't add value
    if (log.includes('TASK [') || log.includes('PLAY [') || 
        log.includes('ok: [') || log.includes('META:') || 
        log.includes('skipping:')) {
      return '';
    }
    
    return log;
  };

  // Enhanced log polling function
  const pollLogs = async (id: string) => {
    try {
      console.log(`Starting log polling for deployment ID: ${id}`);
      setStatus('loading');
      setLogs(['Initializing systemctl operation...']);
      
      // Clean up any existing polling
      if (pollCleanupRef.current) {
        pollCleanupRef.current();
      }
      
      // First, check if deployment exists
      const initialResponse = await fetch(`/api/deploy/${id}/logs`);
      console.log(`Initial response status: ${initialResponse.status}`);
      
      if (initialResponse.status === 404) {
        console.error('Deployment not found');
        setStatus('failed');
        setLogs(['❌ Error: Deployment not found. The operation may not have started correctly.']);
        return;
      }
      
      if (!initialResponse.ok) {
        const errorText = await initialResponse.text();
        console.error(`HTTP Error ${initialResponse.status}: ${errorText}`);
        setStatus('failed');
        setLogs([`❌ Failed to fetch logs: HTTP ${initialResponse.status}`]);
        return;
      }
      
      const initialData = await initialResponse.json();
      console.log('Initial data received:', initialData);
      
      if (initialData.error) {
        setStatus('failed');
        setLogs([`❌ Error: ${initialData.error}`]);
        return;
      }
      
      // Process initial logs
      if (initialData.logs && Array.isArray(initialData.logs)) {
        const processedLogs = initialData.logs
          .map(formatLogMessage)
          .filter((log: string) => log && log.trim() !== '');
        
        if (processedLogs.length > 0) {
          setLogs(processedLogs);
        } else {
          setLogs(['Operation started, waiting for logs...']);
        }
      }
      
      // If operation is already complete, don't start polling
      if (initialData.status && initialData.status !== 'running') {
        console.log(`Operation already completed with status: ${initialData.status}`);
        setStatus(initialData.status);
        addCompletionMessage(initialData.status);
        return;
      }
      
      // Start polling
      let pollCount = 0;
      const maxPollCount = 60; // 60 seconds timeout
      
      const pollInterval = setInterval(async () => {
        try {
          console.log(`Polling attempt ${pollCount + 1}/${maxPollCount}`);
          
          const response = await fetch(`/api/deploy/${id}/logs`);
          
          if (!response.ok) {
            if (response.status === 404) {
              console.log('Deployment completed and cleaned up (404)');
              setStatus('success');
              addCompletionMessage('success');
              clearInterval(pollInterval);
              return;
            }
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
          }
          
          const data = await response.json();
          
          if (data.error) {
            throw new Error(data.error);
          }
          
          // Update logs if available
          if (data.logs && Array.isArray(data.logs)) {
            const processedLogs = data.logs
              .map(formatLogMessage)
              .filter((log: string) => log && log.trim() !== '');
            
            if (processedLogs.length > 0) {
              setLogs(processedLogs);
            }
          }
          
          // Check completion status
          if (data.status && data.status !== 'running') {
            console.log(`Operation completed with status: ${data.status}`);
            setStatus(data.status);
            addCompletionMessage(data.status);
            clearInterval(pollInterval);
            return;
          }
          
          pollCount++;
          
          // Handle timeout
          if (pollCount >= maxPollCount) {
            console.log('Polling timeout reached');
            clearInterval(pollInterval);
            setStatus('timeout');
            setLogs(prev => [...prev, '⚠️ Operation timed out after 60 seconds']);
          }
          
        } catch (error) {
          console.error('Error during polling:', error);
          pollCount += 2; // Increment faster on errors
          
          if (pollCount >= 10) {
            console.log('Too many errors, stopping polling');
            setStatus('failed');
            setLogs(prev => [...prev, `❌ Polling failed: ${error instanceof Error ? error.message : 'Unknown error'}`]);
            clearInterval(pollInterval);
          }
        }
      }, 1000);
      
      // Store cleanup function
      pollCleanupRef.current = () => {
        console.log('Cleaning up polling interval');
        clearInterval(pollInterval);
      };
      
    } catch (error) {
      console.error('Error setting up log polling:', error);
      setStatus('failed');
      setLogs([`❌ Failed to start log polling: ${error instanceof Error ? error.message : 'Unknown error'}`]);
    }
  };

  // Helper function to add completion messages
  const addCompletionMessage = (status: string) => {
    let message = '';
    const icon = status === 'success' ? '✅' : status === 'failed' ? '❌' : '⚠️';
    
    switch (operation) {
      case 'status':
        message = `${icon} Status check for ${selectedService} ${status === 'success' ? 'completed successfully' : 'failed'}`;
        break;
      case 'start':
        message = `${icon} Service ${selectedService} start operation ${status === 'success' ? 'completed successfully' : 'failed'}`;
        break;
      case 'stop':
        message = `${icon} Service ${selectedService} stop operation ${status === 'success' ? 'completed successfully' : 'failed'}`;
        break;
      case 'restart':
        message = `${icon} Service ${selectedService} restart operation ${status === 'success' ? 'completed successfully' : 'failed'}`;
        break;
      default:
        message = `${icon} Operation ${status}`;
    }
    
    setLogs(prev => [...prev, message]);
  };

  // // Debug function for testing the endpoint
  // const debugLogEndpoint = async () => {
  //   if (!deploymentId) {
  //     console.log('No deployment ID available for debugging');
  //     return;
  //   }
    
  //   console.log('=== DEBUG: Testing log endpoint ===');
  //   console.log(`Testing URL: /api/deploy/${deploymentId}/logs`);
    
  //   try {
  //     const response = await fetch(`/api/deploy/${deploymentId}/logs`);
  //     console.log('Response Status:', response.status);
  //     console.log('Response Headers:', Object.fromEntries(response.headers.entries()));
      
  //     const text = await response.text();
  //     console.log('Raw Response:', text);
      
  //     try {
  //       const data = JSON.parse(text);
  //       console.log('Parsed Data:', data);
  //     } catch (parseError) {
  //       console.error('Failed to parse JSON:', parseError);
  //     }
      
  //   } catch (error) {
  //     console.error('Network error:', error);
  //   }
    
  //   console.log('=== END DEBUG ===');
  // };

  // Execute systemctl operation
  const systemctlMutation = useMutation({
    mutationFn: async () => {

      // Get the token from localStorage
      const token = localStorage.getItem('authToken');
      
      if (!token) {
        throw new Error('No authentication token found. Please log in.');
      }
      if (!selectedService || selectedVMs.length === 0) {
        throw new Error('Please select a service and at least one VM');
      }

      const response = await fetch(`/api/systemd/${operation}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          service: selectedService,
          vms: selectedVMs,
          operation
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Failed to execute systemctl operation');
      }

      return response.json();
    },
    onSuccess: (data) => {
      console.log('Systemctl operation response:', data);
      
      toast({
        title: "Systemctl Operation Started",
        description: `Service: ${selectedService}, Operation: ${operation}`,
      });
      
      if (data.deploymentId) {
        setDeploymentId(data.deploymentId);
        setStatus('running');
        pollLogs(data.deploymentId);
      } else {
        console.error('No deploymentId received from server');
        setStatus('failed');
        setLogs(['❌ Error: No deployment ID received from server']);
      }
    },
    onError: (error) => {
      console.error('Systemctl operation error:', error);
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : 'Failed to execute systemctl operation',
        variant: "destructive",
      });
      setStatus('failed');
    },
  });

  // Handle form submission
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Clean up any existing polling
    if (pollCleanupRef.current) {
      pollCleanupRef.current();
      pollCleanupRef.current = null;
    }
    
    setLogs([]);
    setStatus('idle');
    setDeploymentId(null);
    
    systemctlMutation.mutate();
  };

  // Cleanup on component unmount
  React.useEffect(() => {
    return () => {
      if (pollCleanupRef.current) {
        pollCleanupRef.current();
      }
    };
  }, []);

  return (

    
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <Card className="bg-[#1a2b42] text-[#EEEEEE]">
        <CardHeader>
          <CardTitle>Systemctl Operations</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label htmlFor="systemd-service">Service</Label>
              <Select 
                onValueChange={setSelectedService}
                disabled={isLoadingServices || services.length === 0}
              >
                <SelectTrigger id="systemd-service" className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
                  <SelectValue placeholder="Select service" />
                </SelectTrigger>
                <SelectContent>
                  {services.map((service: string) => (
                    <SelectItem key={service} value={service}>{service}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            <div>
              <Label htmlFor="systemd-operation">Operation</Label>
              <Select 
                onValueChange={setOperation}
                defaultValue="status"
              >
                <SelectTrigger id="systemd-operation" className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
                  <SelectValue placeholder="Select operation" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="status">Status</SelectItem>
                  <SelectItem value="start">Start</SelectItem>
                  <SelectItem value="stop">Stop</SelectItem>
                  <SelectItem value="restart">Restart</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <div>
              <Label>Target VMs</Label>
              <VMSelector 
                onSelectionChange={setSelectedVMs}
                selectedVMs={selectedVMs}
              />
            </div>
            
            <Button 
              type="submit" 
              disabled={!selectedService || selectedVMs.length === 0 || systemctlMutation.isPending}
              className="w-full bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
            >
              {systemctlMutation.isPending ? 'Executing...' : 'Execute Systemctl Operation'}
            </Button>
            
            {/* Debug button - remove this in production */}
            {/* {deploymentId && (
              <Button 
                type="button"
                onClick={debugLogEndpoint}
                variant="outline"
                className="w-full mt-2"
              >
                Debug Log Endpoint
              </Button> */}
            {/* )} */}
          </form>
        </CardContent>
      </Card>
      
      <LogDisplay 
        logs={logs} 
        title="Systemctl Operation Logs" 
        height="400px"
        status={status}
      />
    </div>
  );
};

export default SystemctlOperations;
// import React, { useState } from 'react';
// import { useMutation } from '@tanstack/react-query';
// import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
// import { Button } from "@/components/ui/button";
// import { Label } from "@/components/ui/label";
// import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
// import { useToast } from "@/hooks/use-toast";
// import VMSelector from './VMSelector';
// import LogDisplay from './LogDisplay';
// import { useQuery } from '@tanstack/react-query';

// const SystemctlOperations = () => {
//   const { toast } = useToast();
//   const [selectedVMs, setSelectedVMs] = useState<string[]>([]);
//   const [selectedService, setSelectedService] = useState<string>('');
//   const [operation, setOperation] = useState<string>('status');
//   const [logs, setLogs] = useState<string[]>([]);
//   const [deploymentId, setDeploymentId] = useState<string | null>(null);
//   const [status, setStatus] = useState<'idle' | 'loading' | 'running' | 'success' | 'failed'>('idle');

//   // Fetch systemd services
//   const { data: services = [], isLoading: isLoadingServices } = useQuery({
//     queryKey: ['systemd-services'],
//     queryFn: async () => {
//       const response = await fetch('/api/systemd/services');
//       if (!response.ok) {
//         throw new Error('Failed to fetch systemd services');
//       }
//       return response.json();
//     },
//     refetchOnWindowFocus: false,
//   });

//   // Execute systemctl operation
//   const systemctlMutation = useMutation({
//     mutationFn: async () => {
//       if (!selectedService || selectedVMs.length === 0) {
//         throw new Error('Please select a service and at least one VM');
//       }

//       const response = await fetch(`/api/systemd/${operation}`, {
//         method: 'POST',
//         headers: {
//           'Content-Type': 'application/json',
//         },
//         body: JSON.stringify({
//           service: selectedService,
//           vms: selectedVMs,
//           operation
//         }),
//       });

//       if (!response.ok) {
//         const errorText = await response.text();
//         throw new Error(errorText || 'Failed to execute systemctl operation');
//       }

//       return response.json();
//     },
//     onSuccess: (data) => {
//       toast({
//         title: "Systemctl Operation Started",
//         description: `Service: ${selectedService}, Operation: ${operation}`,
//       });
//       setDeploymentId(data.deploymentId);
//       setStatus('running');
//       pollLogs(data.deploymentId);
//     },
//     onError: (error) => {
//       toast({
//         title: "Error",
//         description: error instanceof Error ? error.message : 'Failed to execute systemctl operation',
//         variant: "destructive",
//       });
//     },
//   });

//   // Function to format log messages properly
//   const formatLogMessage = (log: string) => {
//     // Replace template variables with actual values
//     if (log.includes('{ service_name }') || log.includes('{ \'running\' if service_status')) {
//       return `Service ${selectedService} status check completed.`;
//     }
    
//     // Remove ansible-specific output that doesn't add value
//     if (log.includes('TASK [') || log.includes('PLAY [') || 
//         log.includes('ok: [') || log.includes('META:') || 
//         log.includes('skipping:')) {
//       return '';
//     }
    
//     return log;
//   };

//   // Poll for operation logs
//   const pollLogs = async (id: string) => {
//     try {
//       setStatus('loading');
//       // Set up polling for logs instead of SSE which may not work in all environments
//       let pollCount = 0;
//       const pollInterval = setInterval(async () => {
//         try {
//           const response = await fetch(`/api/deploy/${id}/logs`);
//           if (!response.ok) {
//             throw new Error('Failed to fetch logs');
//           }
          
//           const data = await response.json();
          
//           if (data.logs) {
//             // Process logs to remove ansible noise and fix template interpolation
//             const processedLogs = data.logs
//               .map(formatLogMessage)
//               .filter((log: string) => log.trim() !== '');
            
//             // Add operation-specific messages
//             let operationLogs = [...processedLogs];
//             if (operation === 'status' && processedLogs.length > 0) {
//               operationLogs.push(`Status check for ${selectedService} complete.`);
//             } else if (operation === 'start' && data.status !== 'running') {
//               operationLogs.push(`Service ${selectedService} has been started.`);
//             } else if (operation === 'stop' && data.status !== 'running') {
//               operationLogs.push(`Service ${selectedService} has been stopped.`);
//             } else if (operation === 'restart' && data.status !== 'running') {
//               operationLogs.push(`Service ${selectedService} has been restarted.`);
//             }
            
//             setLogs(operationLogs);
//           }
          
//           if (data.status && data.status !== 'running') {
//             setStatus(data.status);
//             clearInterval(pollInterval);
//           }
          
//           pollCount++;
//           if (pollCount > 30) { // Stop after 30 seconds
//             clearInterval(pollInterval);
//             if (data.status === 'running') {
//               setStatus('success'); // Assume success after timeout
//             }
//           }
//         } catch (error) {
//           console.error('Error fetching logs:', error);
//           pollCount += 5;
//           if (pollCount > 10) {
//             setStatus('failed');
//             clearInterval(pollInterval);
//           }
//         }
//       }, 1000);
      
//       return () => clearInterval(pollInterval);
//     } catch (error) {
//       console.error('Error setting up log polling:', error);
//       setStatus('failed');
//     }
//   };

//   // Handle form submission
//   const handleSubmit = (e: React.FormEvent) => {
//     e.preventDefault();
//     setLogs([]);
//     systemctlMutation.mutate();
//   };

//   return (
//     <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
//       <Card className="bg-[#1a2b42] text-[#EEEEEE]">
//         <CardHeader>
//           <CardTitle>Systemctl Operations</CardTitle>
//         </CardHeader>
//         <CardContent>
//           <form onSubmit={handleSubmit} className="space-y-4">
//             <div>
//               <Label htmlFor="systemd-service">Service</Label>
//               <Select 
//                 onValueChange={setSelectedService}
//                 disabled={isLoadingServices || services.length === 0}
//               >
//                 <SelectTrigger id="systemd-service" className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
//                   <SelectValue placeholder="Select service" />
//                 </SelectTrigger>
//                 <SelectContent>
//                   {services.map((service: string) => (
//                     <SelectItem key={service} value={service}>{service}</SelectItem>
//                   ))}
//                 </SelectContent>
//               </Select>
//             </div>
            
//             <div>
//               <Label htmlFor="systemd-operation">Operation</Label>
//               <Select 
//                 onValueChange={setOperation}
//                 defaultValue="status"
//               >
//                 <SelectTrigger id="systemd-operation" className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
//                   <SelectValue placeholder="Select operation" />
//                 </SelectTrigger>
//                 <SelectContent>
//                   <SelectItem value="status">Status</SelectItem>
//                   <SelectItem value="start">Start</SelectItem>
//                   <SelectItem value="stop">Stop</SelectItem>
//                   <SelectItem value="restart">Restart</SelectItem>
//                 </SelectContent>
//               </Select>
//             </div>
            
//             <div>
//               <Label>Target VMs</Label>
//               <VMSelector 
//                 onSelectionChange={setSelectedVMs}
//                 selectedVMs={selectedVMs}
//               />
//             </div>
            
//             <Button 
//               type="submit" 
//               disabled={!selectedService || selectedVMs.length === 0 || systemctlMutation.isPending}
//               className="w-full bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
//             >
//               {systemctlMutation.isPending ? 'Executing...' : 'Execute Systemctl Operation'}
//             </Button>
//           </form>
//         </CardContent>
//       </Card>
      
//       <LogDisplay 
//         logs={logs} 
//         title="Systemctl Operation Logs" 
//         height="400px"
//         status={status}
//       />
//     </div>
//   );
// };

// export default SystemctlOperations;
