
import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useAuth } from '@/contexts/AuthContext';
import LogDisplay from './LogDisplay';
import TemplateFlowchart from './TemplateFlowchart';

interface DeploymentStep {
  type: string;
  description: string;
  order: number;
  ftNumber?: string;
  files?: string[];
  targetPath?: string;
  targetUser?: string;
  targetVMs?: string[];
  dbConnection?: string;
  dbUser?: string;
  dbPassword?: string;
  service?: string;
  operation?: string;
  playbook?: string;
  helmDeploymentType?: string;
  [key: string]: any;
}

interface DeploymentTemplate {
  metadata: {
    ft_number: string;
    generated_at: string;
    description: string;
    total_steps: number;
  };
  steps: DeploymentStep[];
  dependencies: Array<{
    step: number;
    depends_on: number[];
    parallel: boolean;
  }>;
}

interface TemplateInfo {
  name: string;
  description: string;
  ft_number: string;
  total_steps: number;
  steps: Array<{
    order: number;
    type: string;
    description: string;
  }>;
}

const DeployUsingTemplate: React.FC = () => {
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const [loadedTemplate, setLoadedTemplate] = useState<DeploymentTemplate | null>(null);
  const [deploymentId, setDeploymentId] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [logStatus, setLogStatus] = useState<'idle' | 'loading' | 'running' | 'completed' | 'failed'>('idle');
  const { toast } = useToast();

  // Fetch available templates
const { data: templatesData, isLoading: isLoadingTemplates } = useQuery({
  queryKey: ['available-templates'],
  queryFn: async () => {
    console.log("📡 Fetching available templates...");
    const response = await fetch('/api/templates');
    console.log("📡 Status:", response.status);
    if (!response.ok) {
      const errorText = await response.text();
      console.error("❌ Error fetching templates:", errorText);
      throw new Error('Failed to fetch templates');
    }
    const data = await response.json();
    console.log("✅ Templates fetched:", data);
    return data;
  },
  refetchInterval: 30000,
});

const availableTemplates = templatesData?.templates || [];

// Load specific template
const loadTemplateMutation = useMutation({
  mutationFn: async (templateName: string) => {
    console.log("📥 Loading template:", templateName);
    const response = await fetch(`/api/template/${templateName}`);
    console.log("📡 Status:", response.status);
    if (!response.ok) {
      const errorText = await response.text();
      console.error("❌ Error loading template:", errorText);
      throw new Error('Failed to load template');
    }
    const data = await response.json();
    console.log("✅ Template loaded:", data);
    return data;
  },
  onSuccess: (template) => {
    setLoadedTemplate(template);
    console.log("✅ Loaded template state updated:", template);
    toast({
      title: "Success",
      description: `Template ${selectedTemplate} loaded successfully`,
    });
  },
  onError: (error) => {
    console.error("❌ Template load failed:", error);
    toast({
      title: "Error",
      description: `Failed to load template: ${error instanceof Error ? error.message : 'Unknown error'}`,
      variant: "destructive",
    });
  },
});

// Deploy using template
const deployMutation = useMutation({
  mutationFn: async (templateName: string) => {
    const ftNumber = templateName.split('_')[0]; 

    const payload = {
      ft_number: ftNumber,
      template: templateName,
    };
    console.log("🚀 Starting deployment with payload:", payload);

    const response = await fetch('/api/deploy/template', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    console.log("📡 Deploy response status:", response.status);
    if (!response.ok) {
      const errorText = await response.text();
      console.error("❌ Deployment failed with server response:", errorText);
      throw new Error('Failed to start template deployment');
    }

    const data = await response.json();
    console.log("✅ Deployment started:", data);
    return data;
  },
  onSuccess: (data) => {
    setDeploymentId(data.deploymentId);
    setLogStatus('running');
    console.log("✅ Deployment ID:", data.deploymentId);
    // Start polling logs immediately
    if (data.deploymentId) {
      pollLogs(data.deploymentId);
    }
    toast({
      title: "Deployment Started",
      description: `Template deployment initiated with ID: ${data.deploymentId}`,
    });
  },
  onError: (error) => {
    console.error("❌ Deployment error:", error);
    setLogStatus('failed');
    toast({
      title: "Deployment Failed",
      description: `Failed to start deployment: ${error instanceof Error ? error.message : 'Unknown error'}`,
      variant: "destructive",
    });
  },
});

// Poll logs when deployment starts
const pollLogs = async (id: string) => {
  try {
    setLogStatus('loading');
    
    // Set up SSE for real-time logs
    const evtSource = new EventSource(`/api/deploy/${id}/logs`);
    
    evtSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.message) {
        setLogs(prev => [...prev, data.message]);
      }
      
      if (data.status && data.status !== 'running') {
        setLogStatus(data.status === 'success' ? 'completed' : data.status);
        evtSource.close();
      }
    };
    
    evtSource.onerror = () => {
      evtSource.close();
      // Fallback to normal polling if SSE fails
      fetchLogs(id);
    };
    
    return () => {
      evtSource.close();
    };
  } catch (error) {
    console.error('Error setting up log polling:', error);
    // Fallback to regular polling
    fetchLogs(id);
  }
};

const fetchLogs = async (id: string) => {
  try {
    const response = await fetch(`/api/deploy/${id}/logs`);
    if (!response.ok) {
      throw new Error('Failed to fetch logs');
    }
    
    const data = await response.json();
    setLogs(data.logs || []);
    
    if (data.status) {
      setLogStatus(data.status === 'success' ? 'completed' : data.status);
    }
    
    // Continue polling if still running
    if (data.status === 'running') {
      setTimeout(() => fetchLogs(id), 2000);
    }
  } catch (error) {
    console.error('Error fetching logs:', error);
    setLogStatus('failed');
  }
};

const handleLoadTemplate = () => {
  if (!selectedTemplate) {
    toast({
      title: "Error",
      description: "Please select a template",
      variant: "destructive",
    });
    return;
  }

  console.log("🧩 Handle load template:", selectedTemplate);
  loadTemplateMutation.mutate(selectedTemplate);
};

const getStepTypeIcon = (type: string) => {
  switch (type) {
    case 'file_deployment': return '📁';
    case 'sql_deployment': return '🗄️';
    case 'service_restart': return '🔄';
    case 'ansible_playbook': return '🎭';
    case 'helm_upgrade': return '⚙️';
    default: return '📋';
  }
};

const getStepTypeLabel = (type: string) => {
  switch (type) {
    case 'file_deployment': return 'File Deployment';
    case 'sql_deployment': return 'SQL Deployment';
    case 'service_restart': return 'Service Management';
    case 'ansible_playbook': return 'Ansible Playbook';
    case 'helm_upgrade': return 'Helm Upgrade';
    default: return type;
  }
};

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-[#F79B72] mb-4">Deploy using Template</h2>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Left Column - Template Selection and Controls */}
        <div className="xl:col-span-1 space-y-6">
          <Card className="bg-[#1a2b42] text-[#EEEEEE] border-2 border-[#EEEEEE]/30">
            <CardHeader>
              <CardTitle className="text-[#F79B72]">Template Selection</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="template-select" className="text-[#F79B72]">Select Template</Label>
                <Select value={selectedTemplate} onValueChange={setSelectedTemplate}>
                  <SelectTrigger id="template-select" className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30">
                    <SelectValue placeholder={isLoadingTemplates ? "Loading..." : "Select a template"} />
                  </SelectTrigger>
                  <SelectContent>
                    {availableTemplates.map((template: TemplateInfo) => (
                      <SelectItem key={template.name} value={template.name}>
                        {template.ft_number} - {template.description}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <Button
                onClick={handleLoadTemplate}
                disabled={!selectedTemplate || loadTemplateMutation.isPending}
                className="w-full bg-[#2A4759] text-[#EEEEEE] hover:bg-[#2A4759]/80 border-[#EEEEEE]/30"
              >
                {loadTemplateMutation.isPending ? "Loading Template..." : "Load Template"}
              </Button>

              {loadedTemplate && (
                <div className="mt-4 p-3 bg-[#2A4759]/50 rounded-md">
                  <h4 className="text-[#F79B72] font-medium mb-2">Template Info</h4>
                  <div className="text-sm text-[#EEEEEE] space-y-1">
                    <div>FT: {loadedTemplate.metadata.ft_number}</div>
                    <div>Steps: {loadedTemplate.steps.length}</div>
                    <div>Description: {loadedTemplate.metadata.description}</div>
                    <div>Generated: {new Date(loadedTemplate.metadata.generated_at).toLocaleString()}</div>
                  </div>
                </div>
              )}

              <Button
                onClick={() => {
                  if (!selectedTemplate) {
                    toast({
                      title: "Error",
                      description: "Please select a template first",
                      variant: "destructive",
                    });
                    return;
                  }
                  setLogs([]);
                  deployMutation.mutate(selectedTemplate);
                }}
                disabled={!selectedTemplate || deployMutation.isPending || logStatus === 'running'}
                className="w-full bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
              >
                {deployMutation.isPending || logStatus === 'running' ? "Deploying..." : "Deploy"}
              </Button>

              {deploymentId && (
                <div className="mt-4 p-3 bg-[#2A4759]/50 rounded-md">
                  <h4 className="text-[#F79B72] font-medium mb-2">Deployment Status</h4>
                  <div className="text-sm text-[#EEEEEE] space-y-1">
                    <div>ID: {deploymentId}</div>
                    <div>Status: <span className={`capitalize ${
                      logStatus === 'completed' ? 'text-green-400' : 
                      logStatus === 'failed' ? 'text-red-400' :
                      logStatus === 'running' ? 'text-yellow-400' : 'text-gray-400'
                    }`}>{logStatus}</span></div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Template Steps Preview */}
          {loadedTemplate && (
            <Card className="bg-[#1a2b42] text-[#EEEEEE] border-2 border-[#EEEEEE]/30">
              <CardHeader>
                <CardTitle className="text-[#F79B72]">Deployment Steps</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {loadedTemplate.steps
                    .sort((a, b) => a.order - b.order)
                    .map((step, index) => (
                      <div key={step.order} className="flex items-center space-x-3 p-2 bg-[#2A4759]/30 rounded-md">
                        <div className="flex-shrink-0 w-8 h-8 bg-[#F79B72] text-[#2A4759] rounded-full flex items-center justify-center text-sm font-medium">
                          {step.order}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center space-x-2">
                            <span className="text-lg">{getStepTypeIcon(step.type)}</span>
                            <span className="text-sm font-medium text-[#F79B72]">
                              {getStepTypeLabel(step.type)}
                            </span>
                          </div>
                          <p className="text-sm text-[#EEEEEE] truncate">{step.description}</p>
                        </div>
                      </div>
                    ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Middle Column - Flowchart */}
        <div className="xl:col-span-1">
          <Card className="bg-[#1a2b42] text-[#EEEEEE] border-2 border-[#EEEEEE]/30 h-full">
            <CardHeader>
              <CardTitle className="text-[#F79B72]">Deployment Flow</CardTitle>
            </CardHeader>
            <CardContent>
              {loadedTemplate ? (
                <TemplateFlowchart template={loadedTemplate} />
              ) : (
                <div className="flex items-center justify-center h-[500px] text-[#EEEEEE]/50">
                  Load a template to see the deployment flow
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column - Logs */}
        <div className="xl:col-span-1">
          <LogDisplay
            logs={logs}
            height="838px"
            fixedHeight={true}
            title="Template Deployment Logs"
            status={logStatus}
          />
        </div>
      </div>
    </div>
  );
};

export default DeployUsingTemplate;
