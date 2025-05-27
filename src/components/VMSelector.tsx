
import React, { useState } from 'react';
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { useQuery } from '@tanstack/react-query';

interface VMSelectorProps {
  onSelectionChange: (selectedVMs: string[]) => void;
  selectedVMs: string[];
}

const VMSelector: React.FC<VMSelectorProps> = ({ onSelectionChange, selectedVMs }) => {
  // Fetch available VMs
  const { data: vms = [], isLoading } = useQuery({
    queryKey: ['vms'],
    queryFn: async () => {
      const response = await fetch('/api/vms');
      if (!response.ok) {
        throw new Error('Failed to fetch VMs');
      }
      return response.json();
    },
    refetchOnWindowFocus: false,
  });

  const handleVMToggle = (vm: string, checked: boolean) => {
    let newSelection;
    if (checked) {
      newSelection = [...selectedVMs, vm];
    } else {
      newSelection = selectedVMs.filter(v => v !== vm);
    }
    onSelectionChange(newSelection);
  };

  const handleSelectAll = () => {
    onSelectionChange(vms);
  };

  const handleDeselectAll = () => {
    onSelectionChange([]);
  };

  if (isLoading) {
    return <div className="text-[#2A4759]">Loading VMs...</div>;
  }

  return (
    <div className="space-y-2">
      <div className="flex space-x-2 mb-2">
        <button
          type="button"
          onClick={handleSelectAll}
          className="text-xs px-2 py-1 bg-[#F79B72] text-[#2A4759] rounded hover:bg-[#F79B72]/80"
        >
          Select All
        </button>
        <button
          type="button"
          onClick={handleDeselectAll}
          className="text-xs px-2 py-1 bg-[#2A4759] text-white rounded hover:bg-[#2A4759]/80"
        >
          Deselect All
        </button>
      </div>
      
      <div className="grid grid-cols-2 gap-2 max-h-32 overflow-y-auto bg-white/50 p-2 rounded border border-[#2A4759]/20">
        {vms.map((vm: string) => (
          <div key={vm} className="flex items-center space-x-2">
            <Checkbox
              id={`vm-${vm}`}
              checked={selectedVMs.includes(vm)}
              onCheckedChange={(checked) => handleVMToggle(vm, checked === true)}
            />
            <Label htmlFor={`vm-${vm}`} className="text-sm text-[#2A4759]">
              {vm}
            </Label>
          </div>
        ))}
      </div>
      
      {selectedVMs.length > 0 && (
        <div className="text-sm text-[#2A4759]">
          Selected: {selectedVMs.length} VM{selectedVMs.length !== 1 ? 's' : ''}
        </div>
      )}
    </div>
  );
};

export default VMSelector;
