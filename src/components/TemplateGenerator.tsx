
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
import { Trash2, Plus, Edit3 } from "lucide-react";
import VMSelector from './VMSelector';
import DatabaseConnectionSelector from './DatabaseConnectionSelector';
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
  dbName?: string;
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
  const [currentStep, setCurrentStep] = useState<DeploymentStep | null>(null);
  const [isEditingStep, setIsEditingStep] = useState(false);
  const [editingStepId, setEditingStepId] = useState<string | null>(null);
  const [generatedTemplate, setGeneratedTemplate] = useState<any>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editableTemplate, setEditableTemplate] = useState<string>('');
  const [logs, setLogs] = useState<string[]>([]);
  const [isSaving, setIsSaving] = useState(false);
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
  const [stepDbName, setStepDbName] = useState('');
  const [stepDbPassword, setStepDbPassword] = useState('');
  const [stepService, setStepService] = useState('');
  const [stepOperation, setStepOperation] = useState('');
  const [stepPlaybook, setStepPlaybook] = useState('');
  const [stepHelmDeploymentType, setStepHelmDeploymentType] = useState('');

  // Fetch FT numbers
  const { data: fts = [], isLoading: isLoadingFts } = useQuery({
    queryKey: ['fts'],
    queryFn: async () => {
      const response = await fetch('/api/fts');
      if (!response.ok) throw new Error('Failed to fetch FTs');
      return response.json();
    },
  });

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

  // Fetch database connections
  const { data: dbConnections = [] } = useQuery({
    queryKey: ['db-connections'],
    queryFn: async () => {
      const response = await fetch('/api/db-connections');
      if (!response.ok) throw new Error('Failed to fetch database connections');
      return response.json();
    },
  });

  // Fetch database users
  const { data: dbUsers = [] } = useQuery({
    queryKey: ['db-users'],
    queryFn: async () => {
      const response = await fetch('/api/db-users');
      if (!response.ok) throw new Error('Failed to fetch database users');
      return response.json();
    },
  });

  // Fetch systemd services
  const { data: systemdServices = [] } = useQuery({
    queryKey: ['systemd-services'],
    queryFn: async () => {
      const response = await fetch('/api/systemd-services');
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
  const { data: ansiblePlaybooks = [] } = useQuery({
    queryKey: ['ansible-playbooks'],
    queryFn: async () => {
      const response = await fetch('/api/ansible-playbooks');
      if (!response.ok) throw new Error('Failed to fetch ansible playbooks');
      return response.json();
    },
  });

  // Fetch helm deployment types
  const { data: helmDeploymentTypes = [] } = useQuery({
    queryKey: ['helm-deployment-types'],
    queryFn: async () => {
      const response = await fetch('/api/helm-deployment-types');
      if (!response.ok) throw new Error('Failed to fetch helm deployment types');
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
    setStepDbName('');
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

  const handleDbConnectionChange = (connection: { hostname: string; port: string; }) => {
    setStepDbConnection(`${connection.hostname}:${connection.port}`);
  };

  const handleDbUserChange = (user: string) => {
    setStepDbUser(user);
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
      newStep.dbName = stepDbName;
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
    setStepDbName(step.dbName || '');
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
            dbName: stepDbName,
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
              dbName: step.dbName,
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
                  {targetUsers.map((user: string) => (
                    <SelectItem key={user} value={user}>{user}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label className="text-[#F79B72]">Target Path</Label>
              <Input
                value={stepTargetPath}
                onChange={(e) => setStepTargetPath(e.target.value)}
                placeholder="/home/users/abpwrk1/pbin/app"
                className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30"
              />
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
              <DatabaseConnectionSelector
                onConnectionChange={handleDbConnectionChange}
                onUserChange={handleDbUserChange}
                selectedConnection={stepDbConnection}
                selectedUser={stepDbUser}
              />
            </div>

            <div>
              <Label className="text-[#F79B72]">Database Name</Label>
              <Input
                value={stepDbName}
                onChange={(e) => setStepDbName(e.target.value)}
                placeholder="Database name"
                className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30"
              />
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
                {ansiblePlaybooks.map((playbook: string) => (
                  <SelectItem key={playbook} value={playbook}>{playbook}</SelectItem>
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
                {helmDeploymentTypes.map((type: string) => (
                  <SelectItem key={type} value={type}>{type}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-[#F79B72] mb-4">AI Template Generator</h2>
      
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Left Column - Form */}
        <div className="space-y-6">
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
          <Card className="bg-[#1a2b42] text-[#EEEEEE] border-2 border-[#EEEEEE]/30">
            <CardHeader>
              <CardTitle className="text-[#F79B72]">Deployment Steps</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Current Steps List */}
              {steps.length > 0 && (
                <div className="space-y-2">
                  <Label className="text-[#F79B72]">Current Steps:</Label>
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
                      disabled={isSaving}
                      size="sm"
                      className="bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
                    >
                      {isSaving ? "Saving..." : "Save Template"}
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
            status="idle"
          />
        </div>
      </div>
    </div>
  );
};

export default TemplateGenerator;
