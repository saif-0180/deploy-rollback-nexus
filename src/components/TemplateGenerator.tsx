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
import { Trash2, Plus, Edit3, Download, RefreshCw } from "lucide-react";
import VMSelector from './VMSelector';
import LogDisplay from './LogDisplay';

interface DeploymentStep {
  id: string;
  order: number;
  type: string;
  description: string;
  ftNumber?: string;
  selectedFiles?: string[];
  selectedVMs?: string[];
  targetUser?: string;
  targetPath?: string;
  dbConnection?: string;
  dbUser?: string;
  dbPassword?: string;
  service?: string;
  operation?: string;
  playbook?: string;
  helmDeploymentType?: string;
  [key: string]: any;
}

interface TemplateGeneratorProps {
  onTemplateGenerated?: (ftNumber: string, template: any) => void;
}

const TemplateGenerator: React.FC<TemplateGeneratorProps> = ({ onTemplateGenerated }) => {
  const [selectedFt, setSelectedFt] = useState<string>("");
  const [steps, setSteps] = useState<DeploymentStep[]>([]);
  const [generatedTemplate, setGeneratedTemplate] = useState<any>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editableTemplate, setEditableTemplate] = useState<string>('');
  const [logs, setLogs] = useState<string[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [savedTemplates, setSavedTemplates] = useState<string[]>([]);
  const [selectedSavedTemplate, setSelectedSavedTemplate] = useState<string>("");
  const { toast } = useToast();

  // Step form state
  const [stepType, setStepType] = useState('');
  const [stepDescription, setStepDescription] = useState('');
  const [stepFt, setStepFt] = useState('');
  const [stepFiles, setStepFiles] = useState<string[]>([]);
  const [stepVMs, setStepVMs] = useState<string[]>([]);
  const [stepTargetUser, setStepTargetUser] = useState('');
  const [stepTargetPath, setStepTargetPath] = useState('/home/users/abpwrk1/pbin/app');
  const [stepDbConnection, setStepDbConnection] = useState('');
  const [stepDbUser, setStepDbUser] = useState('');
  const [stepDbPassword, setStepDbPassword] = useState('');
  const [stepService, setStepService] = useState('');
  const [stepOperation, setStepOperation] = useState('');
  const [stepPlaybook, setStepPlaybook] = useState('');
  const [stepHelmDeploymentType, setStepHelmDeploymentType] = useState('');
  const [isEditingStep, setIsEditingStep] = useState(false);
  const [editingStepId, setEditingStepId] = useState<string | null>(null);

  // Fetch FT numbers
  const { data: fts = [], isLoading: isLoadingFts } = useQuery({
    queryKey: ['fts'],
    queryFn: async () => {
      const response = await fetch('/api/fts');
      if (!response.ok) throw new Error('Failed to fetch FTs');
      return response.json();
    },
  });

  // Fetch saved templates
  const { data: savedTemplatesData, refetch: refetchSavedTemplates } = useQuery({
    queryKey: ['saved-templates'],
    queryFn: async () => {
      const response = await fetch('/api/templates/list');
      if (!response.ok) throw new Error('Failed to fetch saved templates');
      return response.json();
    },
    refetchInterval: 30000,
  });

  useEffect(() => {
    if (savedTemplatesData) {
      setSavedTemplates(savedTemplatesData);
    }
  }, [savedTemplatesData]);

  // Fetch files for step FT
  const { data: stepFtFiles = [] } = useQuery({
    queryKey: ['files', stepFt],
    queryFn: async () => {
      if (!stepFt) return [];
      const response = await fetch(`/api/fts/${stepFt}/files`);
      if (!response.ok) throw new Error('Failed to fetch files');
      return response.json();
    },
    enabled: !!stepFt,
  });

  // Fetch database connections from db_inventory
  const { data: dbInventory = { db_connections: [], db_users: [] } } = useQuery({
    queryKey: ['db-inventory'],
    queryFn: async () => {
      const response = await fetch('/api/db-inventory');
      if (!response.ok) throw new Error('Failed to fetch database inventory');
      return response.json();
    },
  });

  // Fetch systemd services
  const { data: systemdServices = [] } = useQuery({
    queryKey: ['systemd-services'],
    queryFn: async () => {
      const response = await fetch('/api/systemd/services');
      if (!response.ok) throw new Error('Failed to fetch systemd services');
      return response.json();
    },
  });

  // Fetch target users from inventory
  const { data: targetUsers = [] } = useQuery({
    queryKey: ['target-users'],
    queryFn: async () => {
      const response = await fetch('/api/users');
      if (!response.ok) throw new Error('Failed to fetch users');
      return response.json();
    },
  });

  // Fetch ansible playbooks
  const { data: playbooksData = { playbooks: [] } } = useQuery({
    queryKey: ['playbooks-inventory'],
    queryFn: async () => {
      const response = await fetch('/api/playbooks');
      if (!response.ok) throw new Error('Failed to fetch playbooks');
      return response.json();
    },
  });

  // Fetch helm deployment types
  const { data: helmData = { helm_upgrades: [] } } = useQuery({
    queryKey: ['helm-inventory'],
    queryFn: async () => {
      const response = await fetch('/api/helm-upgrades');
      if (!response.ok) throw new Error('Failed to fetch helm upgrades');
      return response.json();
    },
  });

  const addLog = (message: string) => {
    setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${message}`]);
  };

  const resetStepForm = () => {
    setStepType('');
    setStepDescription('');
    setStepFt('');
    setStepFiles([]);
    setStepVMs([]);
    setStepTargetUser('');
    setStepTargetPath('/home/users/abpwrk1/pbin/app');
    setStepDbConnection('');
    setStepDbUser('');
    setStepDbPassword('');
    setStepService('');
    setStepOperation('');
    setStepPlaybook('');
    setStepHelmDeploymentType('');
  };

  const handleStepFileSelection = (fileName: string, checked: boolean) => {
    setStepFiles(prev => 
      checked 
        ? [...prev, fileName]
        : prev.filter(f => f !== fileName)
    );
  };

  const loadSavedTemplate = async () => {
    if (!selectedSavedTemplate) {
      toast({
        title: "Error",
        description: "Please select a template to load",
        variant: "destructive",
      });
      return;
    }

    try {
      const response = await fetch(`/api/templates/${selectedSavedTemplate}`);
      if (!response.ok) throw new Error('Failed to load template');
      
      const template = await response.json();
      setGeneratedTemplate(template);
      setEditableTemplate(JSON.stringify(template, null, 2));
      
      // Extract FT number from template
      if (template.metadata?.ft_number) {
        setSelectedFt(template.metadata.ft_number);
      }
      
      addLog(`Loaded saved template: ${selectedSavedTemplate}`);
      toast({
        title: "Success",
        description: `Template ${selectedSavedTemplate} loaded successfully`,
      });
    } catch (error) {
      addLog(`Error loading template: ${error instanceof Error ? error.message : 'Unknown error'}`);
      toast({
        title: "Error",
        description: `Failed to load template: ${error instanceof Error ? error.message : 'Unknown error'}`,
        variant: "destructive",
      });
    }
  };

  const addStep = () => {
    if (!stepType || !stepDescription) {
      toast({
        title: "Error",
        description: "Please provide step type and description",
        variant: "destructive",
      });
      return;
    }

    // Validate required fields based on step type
    if (stepType === 'file_deployment' && (!stepFt || stepFiles.length === 0 || !stepTargetUser || stepVMs.length === 0)) {
      toast({
        title: "Error",
        description: "Please fill all required fields for file deployment",
        variant: "destructive",
      });
      return;
    }

    if (stepType === 'sql_deployment' && (!stepFt || stepFiles.length === 0 || !stepDbConnection || !stepDbUser)) {
      toast({
        title: "Error",
        description: "Please fill all required fields for SQL deployment",
        variant: "destructive",
      });
      return;
    }

    if (stepType === 'service_restart' && (!stepService || !stepOperation || stepVMs.length === 0)) {
      toast({
        title: "Error",
        description: "Please fill all required fields for service restart",
        variant: "destructive",
      });
      return;
    }

    if (stepType === 'ansible_playbook' && !stepPlaybook) {
      toast({
        title: "Error",
        description: "Please select a playbook for Ansible deployment",
        variant: "destructive",
      });
      return;
    }

    if (stepType === 'helm_upgrade' && !stepHelmDeploymentType) {
      toast({
        title: "Error",
        description: "Please select a deployment type for Helm upgrade",
        variant: "destructive",
      });
      return;
    }

    const newStep: DeploymentStep = {
      id: `step_${Date.now()}`,
      order: steps.length + 1,
      type: stepType,
      description: stepDescription,
    };

    // Add type-specific fields
    if (stepType === 'file_deployment') {
      newStep.ftNumber = stepFt;
      newStep.selectedFiles = [...stepFiles];
      newStep.selectedVMs = [...stepVMs];
      newStep.targetUser = stepTargetUser;
      newStep.targetPath = stepTargetPath;
    } else if (stepType === 'sql_deployment') {
      newStep.ftNumber = stepFt;
      newStep.selectedFiles = [...stepFiles];
      newStep.dbConnection = stepDbConnection;
      newStep.dbUser = stepDbUser;
      newStep.dbPassword = stepDbPassword ? btoa(stepDbPassword) : ''; // Base64 encode password
    } else if (stepType === 'service_restart') {
      newStep.service = stepService;
      newStep.operation = stepOperation;
      newStep.selectedVMs = [...stepVMs];
    } else if (stepType === 'ansible_playbook') {
      newStep.playbook = stepPlaybook;
    } else if (stepType === 'helm_upgrade') {
      newStep.helmDeploymentType = stepHelmDeploymentType;
    }

    setSteps(prev => [...prev, newStep]);
    resetStepForm();
    addLog(`Added step ${newStep.order}: ${newStep.description}`);
  };

  const editStep = (step: DeploymentStep) => {
    setStepType(step.type);
    setStepDescription(step.description);
    setStepFt(step.ftNumber || '');
    setStepFiles(step.selectedFiles || []);
    setStepVMs(step.selectedVMs || []);
    setStepTargetUser(step.targetUser || '');
    setStepTargetPath(step.targetPath || '/home/users/abpwrk1/pbin/app');
    setStepDbConnection(step.dbConnection || '');
    setStepDbUser(step.dbUser || '');
    setStepDbPassword(''); // Don't decode password for security
    setStepService(step.service || '');
    setStepOperation(step.operation || '');
    setStepPlaybook(step.playbook || '');
    setStepHelmDeploymentType(step.helmDeploymentType || '');
    setEditingStepId(step.id);
    setIsEditingStep(true);
  };

  const updateStep = () => {
    if (!editingStepId) return;

    setSteps(prev => prev.map(step => 
      step.id === editingStepId 
        ? {
            ...step,
            type: stepType,
            description: stepDescription,
            ftNumber: stepFt,
            selectedFiles: [...stepFiles],
            selectedVMs: [...stepVMs],
            targetUser: stepTargetUser,
            targetPath: stepTargetPath,
            dbConnection: stepDbConnection,
            dbUser: stepDbUser,
            dbPassword: stepDbPassword ? btoa(stepDbPassword) : step.dbPassword,
            service: stepService,
            operation: stepOperation,
            playbook: stepPlaybook,
            helmDeploymentType: stepHelmDeploymentType
          }
        : step
    ));

    setIsEditingStep(false);
    setEditingStepId(null);
    resetStepForm();
    addLog(`Updated step`);
  };

  const removeStep = (stepId: string) => {
    setSteps(prev => {
      const filtered = prev.filter(step => step.id !== stepId);
      return filtered.map((step, index) => ({ ...step, order: index + 1 }));
    });
    addLog(`Removed step`);
  };

  const generateTemplate = async () => {
    if (!selectedFt || steps.length === 0) {
      toast({
        title: "Error",
        description: "Please select FT number and add at least one step",
        variant: "destructive",
      });
      return;
    }

    addLog(`Starting template generation for ${selectedFt}`);
    
    try {
      const template = {
        metadata: {
          ft_number: selectedFt,
          generated_at: new Date().toISOString(),
          description: `Deployment template for ${selectedFt}`,
          total_steps: steps.length
        },
        steps: steps.map(step => {
          const baseStep = {
            type: step.type,
            description: step.description,
            order: step.order
          };

          // Add type-specific fields
          if (step.type === 'file_deployment') {
            return {
              ...baseStep,
              ftNumber: step.ftNumber,
              files: step.selectedFiles,
              targetPath: step.targetPath,
              targetUser: step.targetUser,
              targetVMs: step.selectedVMs
            };
          } else if (step.type === 'sql_deployment') {
            return {
              ...baseStep,
              ftNumber: step.ftNumber,
              files: step.selectedFiles,
              dbConnection: step.dbConnection,
              dbUser: step.dbUser,
              dbPassword: step.dbPassword
            };
          } else if (step.type === 'service_restart') {
            return {
              ...baseStep,
              service: step.service,
              operation: step.operation,
              targetVMs: step.selectedVMs
            };
          } else if (step.type === 'ansible_playbook') {
            return {
              ...baseStep,
              playbook: step.playbook
            };
          } else if (step.type === 'helm_upgrade') {
            return {
              ...baseStep,
              helmDeploymentType: step.helmDeploymentType
            };
          }

          return baseStep;
        }),
        dependencies: steps.map((step, index) => ({
          step: index + 1,
          depends_on: index > 0 ? [index] : [],
          parallel: false
        }))
      };

      addLog("Template generated successfully");
      setGeneratedTemplate(template);
      setEditableTemplate(JSON.stringify(template, null, 2));
      
      onTemplateGenerated?.(selectedFt, template);
      toast({
        title: "Success",
        description: `Template for ${selectedFt} generated successfully`,
      });

    } catch (error) {
      addLog(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
      toast({
        title: "Error",
        description: "Failed to generate template",
        variant: "destructive",
      });
    }
  };

  const saveTemplate = async () => {
    if (!generatedTemplate) return;

    setIsSaving(true);
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
          ft_number: selectedFt,
          template: templateToSave
        }),
      });

      if (response.ok) {
        addLog("Template saved successfully");
        toast({
          title: "Success",
          description: `Template for ${selectedFt} saved successfully`,
        });
        setIsEditing(false);
        refetchSavedTemplates();
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
    } finally {
      setIsSaving(false);
    }
  };

  const renderStepForm = () => {
    return (
      <div className="space-y-4">
        {/* Step Type */}
        <div>
          <Label className="text-[#F79B72]">Step Type</Label>
          <Select value={stepType} onValueChange={setStepType}>
            <SelectTrigger className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
              <SelectValue placeholder="Select step type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="file_deployment">File Deployment</SelectItem>
              <SelectItem value="sql_deployment">SQL Deployment</SelectItem>
              <SelectItem value="service_restart">Service Restart</SelectItem>
              <SelectItem value="ansible_playbook">Ansible Playbook</SelectItem>
              <SelectItem value="helm_upgrade">Helm Upgrade</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Step Description */}
        <div>
          <Label className="text-[#F79B72]">Step Description</Label>
          <Input
            value={stepDescription}
            onChange={(e) => setStepDescription(e.target.value)}
            placeholder="Describe what this step does"
            className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30"
          />
        </div>

        {/* File Deployment Fields */}
        {stepType === 'file_deployment' && (
          <>
            <div>
              <Label className="text-[#F79B72]">Select FT</Label>
              <Select value={stepFt} onValueChange={setStepFt}>
                <SelectTrigger className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
                  <SelectValue placeholder="Select FT for this step" />
                </SelectTrigger>
                <SelectContent>
                  {fts.map((ft: string) => (
                    <SelectItem key={ft} value={ft}>{ft}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {stepFt && (
              <div>
                <Label className="text-[#F79B72]">Select Files from {stepFt}</Label>
                <div className="max-h-32 overflow-y-auto bg-[#2A4759] rounded-md p-2 space-y-2">
                  {stepFtFiles.map((file: string) => (
                    <div key={file} className="flex items-center space-x-2">
                      <Checkbox
                        id={`step-file-${file}`}
                        checked={stepFiles.includes(file)}
                        onCheckedChange={(checked) => handleStepFileSelection(file, checked === true)}
                      />
                      <Label htmlFor={`step-file-${file}`} className="text-[#EEEEEE] text-sm">{file}</Label>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div>
              <Label className="text-[#F79B72]">Target User</Label>
              <Select value={stepTargetUser} onValueChange={setStepTargetUser}>
                <SelectTrigger className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
                  <SelectValue placeholder="Select Target User" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="infadm">infadm</SelectItem>
                  <SelectItem value="abpwrk1">abpwrk1</SelectItem>
                  <SelectItem value="admin">admin</SelectItem>
                  <SelectItem value="root">root</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label className="text-[#F79B72]">Target Path</Label>
              <Select value={stepTargetPath} onValueChange={setStepTargetPath}>
                <SelectTrigger className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
                  <SelectValue placeholder="Select Target Path" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="/home/users/abpwrk1/pbin/app">/home/users/abpwrk1/pbin/app</SelectItem>
                  <SelectItem value="/home/users/infadm/bin">/home/users/infadm/bin</SelectItem>
                  <SelectItem value="/opt/app">/opt/app</SelectItem>
                  <SelectItem value="/tmp">/tmp</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label className="text-[#F79B72]">Select VMs</Label>
              <VMSelector
                onSelectionChange={setStepVMs}
                selectedVMs={stepVMs}
              />
            </div>
          </>
        )}

        {/* SQL Deployment Fields */}
        {stepType === 'sql_deployment' && (
          <>
            <div>
              <Label className="text-[#F79B72]">Select FT</Label>
              <Select value={stepFt} onValueChange={setStepFt}>
                <SelectTrigger className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
                  <SelectValue placeholder="Select FT for this step" />
                </SelectTrigger>
                <SelectContent>
                  {fts.map((ft: string) => (
                    <SelectItem key={ft} value={ft}>{ft}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {stepFt && (
              <div>
                <Label className="text-[#F79B72]">Select SQL Files from {stepFt}</Label>
                <div className="max-h-32 overflow-y-auto bg-[#2A4759] rounded-md p-2 space-y-2">
                  {stepFtFiles.filter((file: string) => file.endsWith('.sql')).map((file: string) => (
                    <div key={file} className="flex items-center space-x-2">
                      <Checkbox
                        id={`step-sql-file-${file}`}
                        checked={stepFiles.includes(file)}
                        onCheckedChange={(checked) => handleStepFileSelection(file, checked === true)}
                      />
                      <Label htmlFor={`step-sql-file-${file}`} className="text-[#EEEEEE] text-sm">{file}</Label>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div>
              <Label className="text-[#F79B72]">Database Connection</Label>
              <Select value={stepDbConnection} onValueChange={setStepDbConnection}>
                <SelectTrigger className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
                  <SelectValue placeholder="Select Database Connection" />
                </SelectTrigger>
                <SelectContent>
                  {dbInventory.db_connections?.map((conn: any) => (
                    <SelectItem key={conn.db_connection} value={conn.db_connection}>
                      {conn.db_connection}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label className="text-[#F79B72]">Database User</Label>
              <Select value={stepDbUser} onValueChange={setStepDbUser}>
                <SelectTrigger className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
                  <SelectValue placeholder="Select Database User" />
                </SelectTrigger>
                <SelectContent>
                  {dbInventory.db_users?.map((user: string) => (
                    <SelectItem key={user} value={user}>{user}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label className="text-[#F79B72]">Database Password</Label>
              <Input
                type="password"
                value={stepDbPassword}
                onChange={(e) => setStepDbPassword(e.target.value)}
                placeholder="Enter database password"
                className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30"
              />
            </div>
          </>
        )}

        {/* Service Restart Fields */}
        {stepType === 'service_restart' && (
          <>
            <div>
              <Label className="text-[#F79B72]">Select Service</Label>
              <Select value={stepService} onValueChange={setStepService}>
                <SelectTrigger className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
                  <SelectValue placeholder="Select Service" />
                </SelectTrigger>
                <SelectContent>
                  {systemdServices.map((service: string) => (
                    <SelectItem key={service} value={service}>{service}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label className="text-[#F79B72]">Operation</Label>
              <Select value={stepOperation} onValueChange={setStepOperation}>
                <SelectTrigger className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
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
              <Label className="text-[#F79B72]">Select VMs</Label>
              <VMSelector
                onSelectionChange={setStepVMs}
                selectedVMs={stepVMs}
              />
            </div>
          </>
        )}

        {/* Ansible Playbook Fields */}
        {stepType === 'ansible_playbook' && (
          <div>
            <Label className="text-[#F79B72]">Select Playbook</Label>
            <Select value={stepPlaybook} onValueChange={setStepPlaybook}>
              <SelectTrigger className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
                <SelectValue placeholder="Select Ansible Playbook" />
              </SelectTrigger>
              <SelectContent>
                {playbooksData.playbooks?.map((playbook: any) => (
                  <SelectItem key={playbook.name} value={playbook.name}>{playbook.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {/* Helm Upgrade Fields */}
        {stepType === 'helm_upgrade' && (
          <div>
            <Label className="text-[#F79B72]">Select Deployment Type</Label>
            <Select value={stepHelmDeploymentType} onValueChange={setStepHelmDeploymentType}>
              <SelectTrigger className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
                <SelectValue placeholder="Select Helm Deployment Type" />
              </SelectTrigger>
              <SelectContent>
                {helmData.helm_upgrades?.map((upgrade: any) => (
                  <SelectItem key={upgrade.pod_name} value={upgrade.pod_name}>{upgrade.pod_name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-[#0f1419] p-4">
  <div className="max-w-7xl mx-auto space-y-6">
    <h2 className="text-2xl font-bold text-[#F79B72] mb-4">AI Template Generator</h2>
    
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 min-h-0">
      {/* Left Column - Form and Logs */}
      <div className="space-y-6 flex flex-col">
        {/* Main FT Selection */}
        <Card className="bg-[#1a2b42] text-[#EEEEEE] border-2 border-[#EEEEEE]/30">
          <CardHeader>
            <CardTitle className="text-[#F79B72]">Template Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="main-ft-select" className="text-[#F79B72]">Select FT Number for Template</Label>
              <Select value={selectedFt} onValueChange={setSelectedFt}>
                <SelectTrigger className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
                  <SelectValue placeholder={isLoadingFts ? "Loading..." : "Select FT"} />
                </SelectTrigger>
                <SelectContent>
                  {fts.map((ft: string) => (
                    <SelectItem key={ft} value={ft}>{ft}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* Steps Management */}
        <Card className="bg-[#1a2b42] text-[#EEEEEE] border-2 border-[#EEEEEE]/30 flex-1">
          <CardHeader>
            <CardTitle className="text-[#F79B72]">Deployment Steps</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 h-full flex flex-col">
            {/* Current Steps List */}
            {steps.length > 0 && (
              <div className="space-y-2 flex-1 overflow-y-auto">
                <Label className="text-[#F79B72]">Current Steps:</Label>
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {steps.map((step) => (
                    <div key={step.id} className="flex items-center justify-between bg-[#2A4759]/50 p-3 rounded-md">
                      <div className="flex-1">
                        <div className="text-sm font-medium">Step {step.order}: {step.type.replace(/_/g, ' ')}</div>
                        <div className="text-xs text-[#EEEEEE]/70">{step.description}</div>
                        {step.ftNumber && <div className="text-xs text-[#F79B72]">FT: {step.ftNumber}</div>}
                      </div>
                      <div className="flex space-x-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => editStep(step)}
                          className="border-[#F79B72] text-[#F79B72] hover:bg-[#F79B72]/10"
                        >
                          <Edit3 size={14} />
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => removeStep(step.id)}
                          className="border-red-500 text-red-500 hover:bg-red-500/10"
                        >
                          <Trash2 size={14} />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Step Form */}
            <div className="border-t border-[#EEEEEE]/20 pt-4 space-y-4">
              <Label className="text-[#F79B72]">
                {isEditingStep ? 'Edit Step' : 'Add New Step'}
              </Label>

              {renderStepForm()}

              <div className="flex space-x-2">
                <Button
                  onClick={isEditingStep ? updateStep : addStep}
                  className="bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
                >
                  <Plus size={16} className="mr-2" />
                  {isEditingStep ? 'Update Step' : 'Add Step'}
                </Button>
                {isEditingStep && (
                  <Button
                    onClick={() => {
                      setIsEditingStep(false);
                      setEditingStepId(null);
                      resetStepForm();
                    }}
                    variant="outline"
                    className="border-[#EEEEEE]/30 text-[#EEEEEE]"
                  >
                    Cancel
                  </Button>
                )}
              </div>
            </div>

            <Button
              onClick={generateTemplate}
              disabled={!selectedFt || steps.length === 0}
              className="w-full bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
            >
              Generate Template
            </Button>
          </CardContent>
        </Card>

        {/* Template Generation Logs - At Bottom Left */}
        <div className="flex-shrink-0">
          <LogDisplay
            logs={logs}
            height="300px"
            fixedHeight={true}
            title="Template Generation Logs"
            status="idle"
          />
        </div>
      </div>

      {/* Right Column - Saved Templates and Generated Template */}
      <div className="space-y-6 flex flex-col min-h-0">
        {/* Load Saved Templates */}
        <Card className="bg-[#1a2b42] text-[#EEEEEE] border-2 border-[#EEEEEE]/30 flex-shrink-0">
          <CardHeader>
            <CardTitle className="text-[#F79B72] flex justify-between items-center">
              Load Saved Templates
              <Button
                size="sm"
                variant="outline"
                onClick={() => refetchSavedTemplates()}
                className="border-[#F79B72] text-[#F79B72] hover:bg-[#F79B72]/10"
              >
                <RefreshCw size={14} />
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label className="text-[#F79B72]">Available Templates</Label>
              <Select value={selectedSavedTemplate} onValueChange={setSelectedSavedTemplate}>
                <SelectTrigger className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
                  <SelectValue placeholder="Select a saved template" />
                </SelectTrigger>
                <SelectContent>
                  {savedTemplates.map((template: string) => (
                    <SelectItem key={template} value={template}>{template}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Button
              onClick={loadSavedTemplate}
              disabled={!selectedSavedTemplate}
              className="w-full bg-[#2A4759] text-[#EEEEEE] hover:bg-[#2A4759]/80 border-[#EEEEEE]/30"
            >
              <Download size={16} className="mr-2" />
              Load Template
            </Button>
          </CardContent>
        </Card>
        {/* Generated Template Display/Edit - This will now match the height of the logs */}
        {generatedTemplate && (
          <Card className="bg-[#1a2b42] text-[#EEEEEE] border-2 border-[#EEEEEE]/30 flex-1 flex flex-col">
            <CardHeader className="flex-shrink-0">
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
                    disabled={isSaving}
                    size="sm"
                    className="bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
                  >
                    {isSaving ? "Saving..." : "Save Template"}
                  </Button>
                </div>
              </CardTitle>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col p-4 min-h-0">
              {isEditing ? (
                <Textarea
                  value={editableTemplate}
                  onChange={(e) => setEditableTemplate(e.target.value)}
                  className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30 font-mono text-xs resize-none w-full flex-1 min-h-0"
                />
              ) : (
                <div className="bg-[#2A4759] rounded-md flex-1 overflow-y-auto min-h-0">
                  <pre className="text-xs text-[#EEEEEE] whitespace-pre-wrap p-4">
                    {JSON.stringify(generatedTemplate, null, 2)}
                  </pre>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  </div>
</div>

        
  );
}

export default TemplateGenerator;
