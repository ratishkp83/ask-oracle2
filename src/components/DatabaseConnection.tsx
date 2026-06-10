import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle, CheckCircle2, Database } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useToast } from "@/hooks/use-toast";

interface DatabaseConfig {
  host: string;
  port: string;
  sid: string;
  username: string;
  password: string;
}

interface DatabaseConnectionProps {
  onConfigSave: (config: DatabaseConfig) => void;
  onNext: () => void;
}

export const DatabaseConnection = ({ onConfigSave, onNext }: DatabaseConnectionProps) => {
  const [config, setConfig] = useState<DatabaseConfig>({
    host: "",
    port: "1521",
    sid: "",
    username: "",
    password: ""
  });
  const [isConnected, setIsConnected] = useState(false);
  const [isTestingConnection, setIsTestingConnection] = useState(false);
  const { toast } = useToast();

  const handleInputChange = (field: keyof DatabaseConfig, value: string) => {
    setConfig(prev => ({ ...prev, [field]: value }));
    setIsConnected(false);
  };

  const testConnection = async () => {
    setIsTestingConnection(true);
    
    // Simulate connection test (in real app, this would call your backend)
    setTimeout(() => {
      const isValid = config.host && config.port && config.sid && config.username && config.password;
      
      if (isValid) {
        setIsConnected(true);
        onConfigSave(config);
        toast({
          title: "Connection Successful",
          description: "Successfully connected to Oracle database",
        });
      } else {
        toast({
          title: "Connection Failed",
          description: "Please fill in all required fields",
          variant: "destructive",
        });
      }
      setIsTestingConnection(false);
    }, 2000);
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="host">Host/Server</Label>
          <Input
            id="host"
            placeholder="e.g., oracle.company.com"
            value={config.host}
            onChange={(e) => handleInputChange("host", e.target.value)}
          />
        </div>
        
        <div className="space-y-2">
          <Label htmlFor="port">Port</Label>
          <Input
            id="port"
            placeholder="1521"
            value={config.port}
            onChange={(e) => handleInputChange("port", e.target.value)}
          />
        </div>
        
        <div className="space-y-2">
          <Label htmlFor="sid">SID/Service Name</Label>
          <Input
            id="sid"
            placeholder="e.g., ORCL"
            value={config.sid}
            onChange={(e) => handleInputChange("sid", e.target.value)}
          />
        </div>
        
        <div className="space-y-2">
          <Label htmlFor="username">Username</Label>
          <Input
            id="username"
            placeholder="Database username"
            value={config.username}
            onChange={(e) => handleInputChange("username", e.target.value)}
          />
        </div>
        
        <div className="space-y-2 col-span-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            placeholder="Database password"
            value={config.password}
            onChange={(e) => handleInputChange("password", e.target.value)}
          />
        </div>
      </div>

      {isConnected && (
        <Alert className="border-success bg-success/5">
          <CheckCircle2 className="h-4 w-4 text-success" />
          <AlertDescription className="text-success-foreground">
            Database connection established successfully
          </AlertDescription>
        </Alert>
      )}

      <div className="flex gap-3">
        <Button
          onClick={testConnection}
          disabled={isTestingConnection}
          variant="outline"
          className="flex items-center gap-2"
        >
          <Database className="h-4 w-4" />
          {isTestingConnection ? "Testing..." : "Test Connection"}
        </Button>
        
        <Button
          onClick={onNext}
          disabled={!isConnected}
          className="bg-gradient-primary"
        >
          Continue to Schema Upload
        </Button>
      </div>
    </div>
  );
};