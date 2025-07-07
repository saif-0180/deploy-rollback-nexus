
import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import LogDisplay from './LogDisplay';

interface TemplateGeneratorProps {
  onTemplateGenerated?: (ftNumber: string, template: any) => void;
}

const TemplateGenerator: React.FC<TemplateGeneratorProps> = ({ onTemplateGenerated }) => {
  const [ftNumber, setFtNumber] = useState('');
  const [instructions, setInstructions] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedTemplate, setGeneratedTemplate] = useState<any>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const { toast } = useToast();

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
        const fileMatch = trimmed.match(/(\d+)\s+file[s]?/i);
        const serverMatch = trimmed.match(/(\d+)\s+server[s]?/i);
        
        steps.push({
          type: 'file_deployment',
          description: trimmed,
          fileCount: fileMatch ? parseInt(fileMatch[1]) : 1,
          serverCount: serverMatch ? parseInt(serverMatch[1]) : 1,
          order: steps.length + 1
        });
      }
      
      // Ansible/Playbook operations
      else if (trimmed.includes('playbook') || trimmed.includes('ansible')) {
        steps.push({
          type: 'ansible_playbook',
          description: trimmed,
          playbook: trimmed.match(/run\s+([^\s]+)/i)?.[1] || 'playbook.yml',
          order: steps.length + 1
        });
      }
      
      // Service operations
      else if (trimmed.includes('restart') || trimmed.includes('service')) {
        const serviceMatch = trimmed.match(/restart\s+([^\s]+)/i);
        steps.push({
          type: 'service_restart',
          description: trimmed,
          service: serviceMatch?.[1] || 'service',
          order: steps.length + 1
        });
      }
      
      // Helm operations
      else if (trimmed.includes('helm')) {
        steps.push({
          type: 'helm_upgrade',
          description: trimmed,
          chart: trimmed.match(/upgrade\s+([^\s]+)/i)?.[1] || 'chart',
          order: steps.length + 1
        });
      }
      
      // SQL operations
      else if (trimmed.includes('sql') || trimmed.includes('database') || trimmed.includes('pg')) {
        steps.push({
          type: 'sql_deployment',
          description: trimmed,
          database: trimmed.includes('pg') ? 'postgresql' : 'database',
          order: steps.length + 1
        });
      }
      
      // Configuration changes
      else if (trimmed.includes('change') && trimmed.includes('value')) {
        steps.push({
          type: 'config_change',
          description: trimmed,
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
        description: "Please provide both FT number and instructions",
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
          description: `Deployment template for ${ftNumber}`
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
      
      // Save template to backend
      const response = await fetch('/api/templates/save', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ft_number: ftNumber,
          template: template
        }),
      });

      if (response.ok) {
        addLog("Template saved successfully");
        onTemplateGenerated?.(ftNumber, template);
        toast({
          title: "Success",
          description: `Template for ${ftNumber} generated and saved successfully`,
        });
      } else {
        addLog("Warning: Template generated but failed to save to backend");
      }

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

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-[#F79B72] mb-4">AI Template Generator</h2>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Section */}
        <Card className="bg-[#1a2b42] text-[#EEEEEE] border-2 border-[#EEEEEE]/30">
          <CardHeader>
            <CardTitle className="text-[#F79B72]">Generate Deployment Template</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="ft-number" className="text-[#F79B72]">FT Number</Label>
              <Input
                id="ft-number"
                value={ftNumber}
                onChange={(e) => setFtNumber(e.target.value)}
                placeholder="ft-1987"
                className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30"
              />
            </div>

            <div>
              <Label htmlFor="instructions" className="text-[#F79B72]">Deployment Instructions</Label>
              <Textarea
                id="instructions"
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
                placeholder="Example: ft-1987 has 2 files which needs to be copied on 3 servers, run this playbook and restart certain service"
                className="bg-[#2A4759] text-[#EEEEEE] border-[#EEEEEE]/30 min-h-[200px]"
                rows={10}
              />
            </div>

            <Button
              onClick={generateTemplate}
              disabled={isGenerating}
              className="w-full bg-[#F79B72] text-[#2A4759] hover:bg-[#F79B72]/80"
            >
              {isGenerating ? "Generating Template..." : "Generate Template"}
            </Button>

            {generatedTemplate && (
              <div className="mt-4 p-4 bg-[#2A4759] rounded-md">
                <h4 className="text-[#F79B72] font-medium mb-2">Generated Template Preview</h4>
                <pre className="text-xs text-[#EEEEEE] whitespace-pre-wrap overflow-x-auto">
                  {JSON.stringify(generatedTemplate, null, 2)}
                </pre>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Logs Section */}
        <div>
          <LogDisplay
            logs={logs}
            height="600px"
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
