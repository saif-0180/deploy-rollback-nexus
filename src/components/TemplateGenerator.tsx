
import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { useToast } from "@/hooks/use-toast";
import { useQuery } from "@tanstack/react-query";
import VMSelector from './VMSelector';
import DatabaseConnectionSelector from './DatabaseConnectionSelector';
import LogDisplay from './LogDisplay';

interface TemplateGeneratorProps {
  onTemplateGenerated?: (ftNumber: string, template: any) => void;
}

const TemplateGenerator: React.FC<TemplateGeneratorProps> = ({ onTemplateGenerated }) => {
  const [ftNumber, setFtNumber] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [selectedVMs, setSelectedVMs] = useState<string[]>([]);
  const [selectedDbConnection, setSelectedDbConnection] = useState('');
  const [selectedDbUser, setSelectedDbUser] = useState('');
  const [instructions, setInstructions] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedTemplate, setGeneratedTemplate] = useState<any>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editableTemplate, setEditableTemplate] = useState<string>('');
  const [logs, setLogs] = useState<string[]>([]);
  const { toast } = useToast();

  // Fetch FT numbers
  const { data: ftNumbers = [], isLoading: isLoadingFts } = useQuery({
    queryKey: ['ft-numbers'],
    queryFn: async () => {
      const response = await fetch('/api/ft-numbers');
      if (!response.ok) throw new Error('Failed to fetch FT numbers');
      return response.json();
    },
  });

  // Fetch files for selected FT
  const { data: ftFiles = [], isLoading: isLoadingFiles } = useQuery({
    queryKey: ['ft-files', ftNumber],
    queryFn: async () => {
      if (!ftNumber) return [];
      const response = await fetch(`/api/ft-files/${ftNumber}`);
      if (!response.ok) throw new Error('Failed to fetch FT files');
      return response.json();
    },
    enabled: !!ftNumber,
  });

  // Fetch database connections
  const { data: dbConnections = [], isLoading: isLoadingDbConnections } = useQuery({
    queryKey: ['db-connections'],
    queryFn: async () => {
      const response = await fetch('/api/db-connections');
      if (!response.ok) throw new Error('Failed to fetch database connections');
      return response.json();
    },
  });

  // Fetch database users
  const { data: dbUsers = [], isLoading: isLoadingDbUsers } = useQuery({
    queryKey: ['db-users'],
    queryFn: async () => {
      const response = await fetch('/api/db-users');
      if (!response.ok) throw new Error('Failed to fetch database users');
      return response.json();
    },
  });

  // Fetch systemd services
  const { data: systemdServices = [], isLoading: isLoadingServices } = useQuery({
    queryKey: ['systemd-services'],
    queryFn: async () => {
      const response = await fetch('/api/systemd-services');
      if (!response.ok) throw new Error('Failed to fetch systemd services');
      return response.json();
    },
  });

  const addLog = (message: string) => {
    setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${message}`]);
  };

  const parseInstructions = (text: string) => {
    const steps = [];
    const lines = text.split('\n').filter(line => line.trim());
    
    for (const line of lines) {
      const trimmed = line.trim();
      
      // File operations
      if (trimmed.includes('copy') || trimmed.includes('deploy') || trimmed.includes('file')) {
        const fileMatch = trimmed.match(/(\w+\.\w+)/g);
        const pathMatch = trimmed.match(/path\s+([^\s]+)/i);
        const userMatch = trimmed.match(/user\s+(\w+)/i);
        const vmMatch = trimmed.match(/to\s+(\w+)/i);
        
        steps.push({
          type: 'file_deployment',
          description: trimmed,
          files: fileMatch || [],
          targetPath: pathMatch?.[1] || '/home/users/abpwrk1/pbin/app',
          targetUser: userMatch?.[1] || 'abpwrk1',
          targetVMs: vmMatch ? [vmMatch[1]] : selectedVMs,
          order: steps.length + 1
        });
      }
      
      // SQL operations
      else if (trimmed.includes('sql') || trimmed.includes('query') || trimmed.includes('database')) {
        const sqlFileMatch = trimmed.match(/(\w+\.sql)/i);
        
        steps.push({
          type: 'sql_deployment',
          description: trimmed,
          sqlFile: sqlFileMatch?.[1] || 'query.sql',
          dbConnection: selectedDbConnection,
          dbUser: selectedDbUser,
          order: steps.length + 1
        });
      }
      
      // Service operations
      else if (trimmed.includes('restart') || trimmed.includes('service')) {
        const serviceMatch = trimmed.match(/restart\s+([^\s]+)/i);
        
        steps.push({
          type: 'service_restart',
          description: trimmed,
          service: serviceMatch?.[1] || 'docker.service',
          targetVMs: selectedVMs,
          order: steps.length + 1
        });
      }
      
      // Playbook operations
      else if (trimmed.includes('playbook') || trimmed.includes('ansible')) {
        const playbookMatch = trimmed.match(/playbook\s+([^\s]+)/i);
        
        steps.push({
          type: 'ansible_playbook',
          description: trimmed,
          playbook: playbookMatch?.[1] || 'playbook.yml',
          targetVMs: selectedVMs,
          order: steps.length + 1
        });
      }
      
      // Helm operations
      else if (trimmed.includes('helm')) {
        const chartMatch = trimmed.match(/upgrade\s+([^\s]+)/i);
        
        steps.push({
          type: 'helm_upgrade',
          description: trimmed,
          chart: chartMatch?.[1] || 'chart',
          targetVMs: selectedVMs,
          order: steps.length + 1
        });
      }
    }
    
    return steps;
  };

  const generateTemplate = async () => {
    if (!ftNumber || !instructions) {
      toast({
        title: "Error",
        description: "Please provide FT number and instructions",
        variant: "destructive",
      });
      return;
    }

    setIsGenerating(true);
    setLogs([]);
    addLog(`Starting template generation for ${ftNumber}`);
    
    try {
      addLog("Parsing deployment instructions...");
      const steps = parseInstructions(instructions);
      addLog(`Identified ${steps.length} deployment steps`);

      const template = {
        metadata: {
          ft_number: ftNumber,
          generated_at: new Date().toISOString(),
          description: `Deployment template for ${ftNumber}`,
          selectedFiles: selectedFiles,
          selectedVMs: selectedVMs,
          dbConnection: selectedDbConnection,
          dbUser: selectedDbUser
        },
        steps: steps,
        dependencies: steps.map((step, index) => ({
          step: index + 1,
          depends_on: index > 0 ? [index] : [],
          parallel: false
        }))
      };

      addLog("Template generated successfully");
      setGeneratedTemplate(template);
      setEditableTemplate(JSON.stringify(template, null, 2));
      
      onTemplateGenerated?.(ftNumber, template);
      toast({
        title: "Success",
        description: `Template for ${ftNumber} generated successfully`,
      });

    } catch (error) {
      addLog(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
      toast({
        title: "Error",
        description: "Failed to generate template",
        variant: "destructive",
      });
    } finally {
      setIsGenerating(false);
    }
  };

  const saveTemplate = async () => {
    if (!generatedTemplate) return;

    try {
      let templateToSave = generatedTemplate;
      
      if (isEditing) {
        templateToSave = JSON.parse(editableTemplate);
      }

      const response = await fetch('/api/templates/save', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ft_number: ftNumber,
          template: templateToSave
        }),
      });

      if (response.ok) {
        addLog("Template saved successfully");
        toast({
          title: "Success",
          description: `Template for ${ftNumber} saved successfully`,
        });
        setIsEditing(false);
      } else {
        throw new Error('Failed to save template');
      }
    } catch (error) {
      addLog(`Error saving template: ${error instanceof Error ? error.message : 'Unknown error'}`);
      toast({
        title: "Error",
        description: "Failed to save template",
        variant: "destructive",
      });
    }
  };

  const handleFileSelection = (fileName: string, checked: boolean) => {
    setSelectedFiles(prev => 
      checked 
        ? [...prev, fileName]
        : prev.filter(f => f !== fileName)
    );
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-[#F79B72] mb-4">AI Template Generator</h2>
      
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Left Column - Form */}
        <div className="space-y-6">
          <Card className="bg-[#1a2b42] text-[#EEEEEE] border-2 border-[#EEEEEE]/30">
            <CardHeader>
              <CardTitle className="text-[#F79B72]">Template Configuration</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* FT Number Selection */}
              <div>
                <Label htmlFor="ft-select" className="text-[#F79B72]">Select FT Number</Label>
                <Select value={ftNumber} onValueChange={setFtNumber}>
                  <SelectTrigger className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
                    <SelectValue placeholder={isLoadingFts ? "Loading..." : "Select FT"} />
                  </SelectTrigger>
                  <SelectContent>
                    {ftNumbers.map((ft: string) => (
                      <SelectItem key={ft} value={ft}>{ft}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* File Selection */}
              {ftNumber && (
                <div>
                  <Label className="text-[#F79B72]">Select Files</Label>
                  <div className="max-h-32 overflow-y-auto bg-[#2A4759] rounded-md p-2 space-y-2">
                    {isLoadingFiles ? (
                      <div className="text-[#EEEEEE]">Loading files...</div>
                    ) : (
                      ftFiles.map((file: string) => (
                        <div key={file} className="flex items-center space-x-2">
                          <Checkbox
                            id={`file-${file}`}
                            checked={selectedFiles.includes(file)}
                            onCheckedChange={(checked) => handleFileSelection(file, checked === true)}
                          />
                          <Label htmlFor={`file-${file}`} className="text-[#EEEEEE] text-sm">{file}</Label>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}

              {/* VM Selection */}
              <div>
                <Label className="text-[#F79B72]">Select VMs</Label>
                <VMSelector
                  onSelectionChange={setSelectedVMs}
                  selectedVMs={selectedVMs}
                />
              </div>

              {/* Database Connection */}
              <div>
                <Label className="text-[#F79B72]">Database Connection (Optional)</Label>
                <DatabaseConnectionSelector
                  onConnectionChange={setSelectedDbConnection}
                  onUserChange={setSelectedDbUser}
                  selectedConnection={selectedDbConnection}
                  selectedUser={selectedDbUser}
                />
              </div>

              {/* Instructions */}
              <div>
                <Label htmlFor="instructions" className="text-[#F79B72]">Deployment Instructions</Label>
                <Textarea
                  id="instructions"
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                  placeholder="Example: copy file1 to batch1 path /home/users/abpwrk1/pbin/app user abpwrk1, then restart docker.service, then copy file2 to batch2 and imdg1 path /home/users/abpwrk1/pbin/app, then run playbook playbook1.yaml"
                  className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30 min-h-[150px]"
                  rows={8}
                />
              </div>

              <Button
                onClick={generateTemplate}
                disabled={isGenerating}
                className="w-full bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
              >
                {isGenerating ? "Generating Template..." : "Generate Template"}
              </Button>
            </CardContent>
          </Card>

          {/* Template Display/Edit */}
          {generatedTemplate && (
            <Card className="bg-[#1a2b42] text-[#EEEEEE] border-2 border-[#EEEEEE]/30">
              <CardHeader>
                <CardTitle className="text-[#F79B72] flex justify-between items-center">
                  Generated Template
                  <div className="space-x-2">
                    <Button
                      onClick={() => setIsEditing(!isEditing)}
                      size="sm"
                      variant="outline"
                      className="border-[#F79B72] text-[#F79B72] hover:bg-[#F79B72]/10"
                    >
                      {isEditing ? "Cancel Edit" : "Edit"}
                    </Button>
                    <Button
                      onClick={saveTemplate}
                      size="sm"
                      className="bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
                    >
                      Save Template
                    </Button>
                  </div>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {isEditing ? (
                  <Textarea
                    value={editableTemplate}
                    onChange={(e) => setEditableTemplate(e.target.value)}
                    className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30 min-h-[400px] font-mono text-xs"
                    rows={20}
                  />
                ) : (
                  <pre className="text-xs text-[#EEEEEE] whitespace-pre-wrap overflow-x-auto bg-[#2A4759] p-4 rounded-md max-h-[400px] overflow-y-auto">
                    {JSON.stringify(generatedTemplate, null, 2)}
                  </pre>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right Column - Logs */}
        <div>
          <LogDisplay
            logs={logs}
            height="838px"
            fixedHeight={true}
            title="Template Generation Logs"
            status={isGenerating ? 'running' : 'idle'}
          />
        </div>
      </div>
    </div>
  );
};

export default TemplateGenerator;
