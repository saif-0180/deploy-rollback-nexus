
import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";

interface DBConnection {
  hostname: string;
  port: string;
  users: string[];
}

interface DatabaseConnectionSelectorProps {
  onConnectionChange: (connection: { hostname: string; port: string; }) => void;
  onUserChange: (user: string) => void;
  selectedHostname?: string;
  selectedPort?: string;
  selectedUser?: string;
}

const DatabaseConnectionSelector: React.FC<DatabaseConnectionSelectorProps> = ({
  onConnectionChange,
  onUserChange,
  selectedHostname = "",
  selectedPort = "",
  selectedUser = ""
}) => {
  const [availableUsers, setAvailableUsers] = useState<string[]>([]);
  const [customHostname, setCustomHostname] = useState<string>("");
  const [customPort, setCustomPort] = useState<string>("");
  const [useCustomConnection, setUseCustomConnection] = useState<boolean>(false);

  // Fetch DB connections from API
  const { data: dbConnections = [], isLoading: isLoadingConnections } = useQuery({
    queryKey: ['db-connections'],
    queryFn: async () => {
      try {
        const response = await fetch('/api/db/connections');
        if (!response.ok) {
          throw new Error('Failed to fetch DB connections from API');
        }
        const data = await response.json();
        console.log('Fetching DB connections from inventory', data);
        return data;
      } catch (error) {
        console.error('Error fetching DB connections:', error);
        return [];
      }
    },
    refetchOnWindowFocus: false,
  });

  // Fetch DB users from API
  const { data: dbUsers = [], isLoading: isLoadingUsers } = useQuery({
    queryKey: ['db-users'],
    queryFn: async () => {
      try {
        const response = await fetch('/api/db/users');
        if (!response.ok) {
          throw new Error('Failed to fetch DB users from API');
        }
        const data = await response.json();
        console.log('Fetching DB users from inventory', data);
        return data;
      } catch (error) {
        console.error('Error fetching DB users from API:', error);
        return [];
      }
    },
    refetchOnWindowFocus: false,
  });

  // Handle connection selection
  const handleConnectionChange = (hostname: string, port: string) => {
    // Find the connection to get available users
    const connection = dbConnections.find(
      (conn: DBConnection) => conn.hostname === hostname && conn.port === port
    );
    
    if (connection && connection.users) {
      console.log('Setting available users for connection:', hostname, connection.users);
      setAvailableUsers(connection.users);
    } else {
      setAvailableUsers(dbUsers);
    }

    onConnectionChange({ hostname, port });
  };

  // Handle selection of a predefined connection
  const handlePredefinedConnectionChange = (value: string) => {
    if (value === "custom") {
      setUseCustomConnection(true);
      return;
    }
    
    setUseCustomConnection(false);
    const [hostname, port] = value.split(":");
    handleConnectionChange(hostname, port);
  };

  // Handle custom connection changes
  useEffect(() => {
    if (useCustomConnection && customHostname && customPort) {
      handleConnectionChange(customHostname, customPort);
    }
  }, [useCustomConnection, customHostname, customPort]);

  // Initialize with selected values or first connection if available
  useEffect(() => {
    if (selectedHostname && selectedPort) {
      handleConnectionChange(selectedHostname, selectedPort);
    } else if (dbConnections.length > 0 && !useCustomConnection) {
      const firstConn = dbConnections[0] as DBConnection;
      handleConnectionChange(firstConn.hostname, firstConn.port);
    }
  }, [dbConnections, selectedHostname, selectedPort]);

  if (isLoadingConnections || isLoadingUsers) {
    return <div>Loading database connections...</div>;
  }

  // Create connection options for the dropdown
  const connectionOptions = dbConnections.map((conn: DBConnection) => ({
    value: `${conn.hostname}:${conn.port}`,
    label: `${conn.hostname}:${conn.port}`
  }));

  // Add custom option
  connectionOptions.push({ value: "custom", label: "Custom Connection" });

  return (
    <div className="space-y-4">
      <div>
        <Label htmlFor="db-connection">Database Connection</Label>
        <Select 
          onValueChange={handlePredefinedConnectionChange}
          defaultValue={connectionOptions[0]?.value}
        >
          <SelectTrigger id="db-connection">
            <SelectValue placeholder="Select a connection" />
          </SelectTrigger>
          <SelectContent>
            {connectionOptions.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {useCustomConnection && (
        <div className="space-y-2">
          <div>
            <Label htmlFor="custom-hostname">Custom Hostname</Label>
            <Input 
              id="custom-hostname"
              value={customHostname}
              onChange={(e) => setCustomHostname(e.target.value)}
              placeholder="Enter hostname"
            />
          </div>
          <div>
            <Label htmlFor="custom-port">Custom Port</Label>
            <Input 
              id="custom-port"
              value={customPort}
              onChange={(e) => setCustomPort(e.target.value)}
              placeholder="Enter port"
            />
          </div>
        </div>
      )}

      <div>
        <Label htmlFor="db-user">Database User</Label>
        <Select 
          onValueChange={onUserChange}
          defaultValue={selectedUser || availableUsers[0]}
        >
          <SelectTrigger id="db-user">
            <SelectValue placeholder="Select a user" />
          </SelectTrigger>
          <SelectContent>
            {availableUsers.map((user) => (
              <SelectItem key={user} value={user}>
                {user}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
};

export default DatabaseConnectionSelector;
