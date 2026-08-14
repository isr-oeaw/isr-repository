from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import Dataset, DatasetCategory, DatasetVersion, Comment, Publisher, DatasetAnalysis
from projects.models import Project

User = get_user_model()


class DatasetForm(forms.ModelForm):
    """Form for creating and editing datasets"""
    
    class Meta:
        model = Dataset
        fields = [
            'title', 'description', 'abstract', 'category', 'tags',
            'status', 'access_level', 'license',
            'citation', 'doi', 'publisher', 'uri_ref', 'contributors', 'related_datasets', 'projects'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter dataset title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Detailed description of the dataset'
            }),
            'abstract': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Brief summary of the dataset'
            }),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter tags separated by commas'
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'access_level': forms.Select(attrs={'class': 'form-select'}),
            'license': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., CC BY 4.0, MIT License'
            }),
            'citation': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'How to cite this dataset'
            }),
            'doi': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Digital Object Identifier'
            }),
                'publisher': forms.Select(attrs={
                    'class': 'form-select'
                }),
            'uri_ref': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com/dataset-identifier'
            }),
            'contributors': forms.SelectMultiple(attrs={
                'class': 'form-select',
                'size': 5
            }),
            'related_datasets': forms.SelectMultiple(attrs={
                'class': 'form-select',
                'size': 5
            }),
            'projects': forms.SelectMultiple(attrs={
                'class': 'form-select',
                'size': 5
            })
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Limit contributors to active users
        self.fields['contributors'].queryset = User.objects.filter(is_active=True)
        
        # Only show active categories
        self.fields['category'].queryset = DatasetCategory.objects.filter(is_active=True)
        
        # Only show active publishers
        self.fields['publisher'].queryset = Publisher.objects.filter(is_active=True)
        self.fields['publisher'].empty_label = "Select a publisher..."
        
        # Configure related datasets queryset
        if self.instance.pk:
            # When editing, exclude the current dataset from related datasets
            self.fields['related_datasets'].queryset = Dataset.objects.exclude(pk=self.instance.pk)
        else:
            # When creating, show all datasets
            self.fields['related_datasets'].queryset = Dataset.objects.all()
        
        # Configure projects queryset based on user access
        if user and user.is_authenticated:
            # Show all projects if superuser, otherwise show projects the user owns or collaborates on
            if user.is_superuser:
                self.fields['projects'].queryset = Project.objects.all()
            else:
                accessible_projects = Project.objects.filter(
                    Q(owner=user) | Q(collaborators=user) | Q(access_level='public')
                ).distinct()
                self.fields['projects'].queryset = accessible_projects
        else:
            # No projects if user is not authenticated
            self.fields['projects'].queryset = Project.objects.none()

    def clean_tags(self):
        tags = self.cleaned_data.get('tags')
        if tags:
            # Clean and validate tags
            tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
            if len(tag_list) > 10:
                raise forms.ValidationError('Maximum 10 tags allowed.')
            return ', '.join(tag_list)
        return tags


class DatasetFilterForm(forms.Form):
    """Form for filtering datasets"""
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search datasets...'
        })
    )
    category = forms.ModelChoiceField(
        queryset=DatasetCategory.objects.filter(is_active=True),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    tags = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Filter by tags...'
        })
    )
    access_level = forms.ChoiceField(
        choices=[('', 'All Access Levels')] + Dataset.ACCESS_LEVEL_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    sort_by = forms.ChoiceField(
        choices=[
            ('-created_at', 'Newest First'),
            ('created_at', 'Oldest First'),
            ('-download_count', 'Most Downloaded'),
            ('title', 'Title A-Z'),
            ('-title', 'Title Z-A'),
        ],
        required=False,
        initial='-created_at',
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class DatasetCategoryForm(forms.ModelForm):
    """Form for creating and editing dataset categories"""
    
    class Meta:
        model = DatasetCategory
        fields = ['name', 'description', 'color', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Category name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Category description'
            }),
            'color': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'color'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            # Check for duplicate names (excluding current instance)
            queryset = DatasetCategory.objects.filter(name__iexact=name)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise forms.ValidationError('A category with this name already exists.')
        return name


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultiFileField(forms.FileField):
    def clean(self, data, initial=None):
        if data is None:
            data = []
        if isinstance(data, (list, tuple)):
            files = list(data)
        else:
            files = [data] if data else []

        cleaned_files = []
        errors = []

        for uploaded_file in files:
            if uploaded_file in (None, ''):
                continue
            try:
                cleaned_files.append(super().clean(uploaded_file, initial))
            except forms.ValidationError as exc:
                errors.extend(exc.error_list)

        if errors:
            raise forms.ValidationError(errors)

        if self.required and not cleaned_files:
            raise forms.ValidationError(self.error_messages['required'], code='required')

        return cleaned_files


class DatasetVersionForm(forms.ModelForm):
    """Form for creating new dataset versions"""
    
    # Add a choice field for input method
    input_method = forms.ChoiceField(
        choices=[
            ('upload', 'Upload File'),
            ('url', 'External URL')
        ],
        initial='upload',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    files = MultiFileField(
        required=False,
        widget=MultiFileInput(attrs={
            'class': 'form-control',
            'multiple': True,
            'accept': '.csv,.sav,.zsav,.por,.dta,.rds,.json,.xlsx,.xls,.txt,.zip,.tar.gz,.gpkg,.shp,.shx,.dbf,.prj,.sbn,.sbx,.shp.xml,.cpg,.geojson,.kml,.kmz,.tif,.tiff,.jpg,.jpeg,.png,.img,.gdb,.mdb,.lyr,.lyrx,.mpk,.mpkx,.qgs,.qgz,.qml,.sqlite,.sql,.pdf'
        })
    )
    
    class Meta:
        model = DatasetVersion
        fields = ['version_number', 'description', 'file_url', 'file_url_description', 'file_size_text']
        widgets = {
            'version_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 1.1, 2.0, 1.2.3'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe the changes in this version...'
            }),
            'file_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com/dataset.zip'
            }),
            'file_url_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe where the file is located (e.g., "GitHub repository", "University server", "Cloud storage")'
            }),
            'file_size_text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 2.5 MB, 1.2 GB'
            })
        }

    def __init__(self, *args, **kwargs):
        self.dataset = kwargs.pop('dataset', None)
        super().__init__(*args, **kwargs)
        
        # Add help text for fields
        self.fields['version_number'].help_text = 'Use semantic versioning (e.g., 1.0, 1.1, 2.0)'
        self.fields['description'].help_text = 'Optional: Describe what changed in this version'
        max_upload_gb = settings.MAX_DATASET_UPLOAD_SIZE // (1024 * 1024 * 1024)
        self.fields['files'].help_text = (
            'Upload one or more files for this version (CSV, SPSS (.sav, .zsav, .por), Stata (.dta), R (.rds), '
            'JSON, Excel, TXT, ZIP, TAR.GZ, GPKG, Shapefile, GeoJSON, KML/KMZ, Raster formats, File/Personal '
            f'Geodatabase, Esri Layer Files, Esri Map Packages, QGIS Project Files, QML, SpatiaLite, SQL, PDF '
            f'formats supported, max {max_upload_gb}GB total)'
        )
        self.fields['file_url'].help_text = 'External URL where the file can be accessed'
        self.fields['file_url_description'].help_text = 'Optional: Describe where the file is located'
        self.fields['file_size_text'].help_text = 'Human-readable file size (e.g., "2.5 MB", "1.2 GB")'
        
        # Set initial field order
        self.fields['input_method'].label = 'File Input Method'

    def clean_version_number(self):
        version_number = self.cleaned_data.get('version_number')
        if version_number and self.dataset:
            # Check if version number already exists for this dataset
            if DatasetVersion.objects.filter(
                dataset=self.dataset, 
                version_number=version_number
            ).exists():
                raise forms.ValidationError(
                    f'Version {version_number} already exists for this dataset.'
                )
        return version_number

    def clean(self):
        cleaned_data = super().clean()
        input_method = cleaned_data.get('input_method')
        uploaded_files = cleaned_data.get('files') or []
        file_url = cleaned_data.get('file_url')
        file_url_description = cleaned_data.get('file_url_description')
        file_size_text = cleaned_data.get('file_size_text')
        total_upload_size = 0
        
        # Validate based on input method
        if input_method == 'upload':
            if not uploaded_files:
                self.add_error('files', 'Please upload at least one file when using the upload method.')
                raise forms.ValidationError('Please upload at least one file when using the upload method.')
            if file_url:
                raise forms.ValidationError('Please do not provide a URL when uploading a file.')
            if file_size_text:
                raise forms.ValidationError('File size will be calculated automatically when uploading.')
            
            max_upload_size = settings.MAX_DATASET_UPLOAD_SIZE
            max_upload_gb = max_upload_size // (1024 * 1024 * 1024)

            for upload in uploaded_files:
                if upload.size > max_upload_size:
                    size_gb = upload.size / (1024 * 1024 * 1024)
                    self.add_error(
                        'files',
                        f'File "{upload.name}" ({size_gb:.2f} GB) exceeds the {max_upload_gb}GB size limit.',
                    )
                    raise forms.ValidationError(f'Each uploaded file must be {max_upload_gb}GB or smaller.')

                total_upload_size += upload.size

            if total_upload_size > max_upload_size:
                total_gb = total_upload_size / (1024 * 1024 * 1024)
                self.add_error(
                    'files',
                    f'Total upload size ({total_gb:.2f} GB) exceeds the {max_upload_gb}GB limit.',
                )
                raise forms.ValidationError(f'Total upload size must be {max_upload_gb}GB or smaller.')

            # Update file_size field with total upload size
            self.instance.file_size = total_upload_size
            
        elif input_method == 'url':
            # Either URL or description must be provided (or both)
            if not file_url and not file_url_description:
                raise forms.ValidationError('Please provide either a URL or description (or both) when using the external URL method.')
            if uploaded_files:
                raise forms.ValidationError('Please do not upload files when using the external URL method.')
            if not file_size_text:
                raise forms.ValidationError('Please provide the file size when using external URL.')
            
            self.instance.file_size = 0
        
        cleaned_data['uploaded_files'] = uploaded_files
        cleaned_data['uploaded_files_total_size'] = total_upload_size
        return cleaned_data


class DatasetCategoryForm(forms.ModelForm):
    """Form for creating and editing dataset categories"""
    
    class Meta:
        model = DatasetCategory
        fields = ['name', 'description', 'color', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter category name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe this category...'
            }),
            'color': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'color',
                'placeholder': '#007bff'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add help text for fields
        self.fields['name'].help_text = 'Unique name for the category'
        self.fields['description'].help_text = 'Optional description of the category'
        self.fields['color'].help_text = 'Color for the category badge'
        self.fields['is_active'].help_text = 'Whether this category is active and available for selection'

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            # Check for duplicate names (excluding current instance)
            queryset = DatasetCategory.objects.filter(name__iexact=name)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            
            if queryset.exists():
                raise forms.ValidationError('A category with this name already exists.')
        
        return name


class DatasetCategoryFilterForm(forms.Form):
    """Form for filtering categories"""
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search categories...'
        })
    )
    is_active = forms.ChoiceField(
        choices=[('', 'All'), ('true', 'Active'), ('false', 'Inactive')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class CommentForm(forms.ModelForm):
    """Form for creating and editing comments"""
    
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Share your thoughts about this dataset...',
                'maxlength': 1000
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.dataset = kwargs.pop('dataset', None)
        super().__init__(*args, **kwargs)
        
        # Add help text
        self.fields['content'].help_text = 'Maximum 1000 characters'
    
    def clean_content(self):
        content = self.cleaned_data.get('content')
        if content and len(content.strip()) < 10:
            raise forms.ValidationError('Comment must be at least 10 characters long.')
        return content.strip()


class CommentEditForm(forms.ModelForm):
    """Form for editing existing comments"""
    
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Edit your comment...',
                'maxlength': 1000
            })
        }
    
    def clean_content(self):
        content = self.cleaned_data.get('content')
        if content and len(content.strip()) < 10:
            raise forms.ValidationError('Comment must be at least 10 characters long.')
        return content.strip()


class PublisherForm(forms.ModelForm):
    """Form for creating and editing publishers"""
    
    class Meta:
        model = Publisher
        fields = ['name', 'description', 'website', 'is_active', 'is_default']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., University of Vienna, Research Institute'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional description of the publisher'
            }),
            'website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_default': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].label = 'Name'
        self.fields['description'].label = 'Description'
        self.fields['website'].label = 'Website'
        self.fields['is_active'].label = 'Active'
        self.fields['is_default'].label = 'Default'
        
        # Add help text
        self.fields['name'].help_text = 'Name of the publisher'
        self.fields['description'].help_text = 'Optional description'
        self.fields['website'].help_text = 'Official website URL'
        self.fields['is_active'].help_text = 'Whether this publisher is available for selection'
        self.fields['is_default'].help_text = 'Whether this is the default publisher for new datasets'


class PublisherFilterForm(forms.Form):
    """Form for filtering publishers"""
    name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search publishers...'
        })
    )
    is_active = forms.ChoiceField(
        choices=[('', 'All'), ('true', 'Active'), ('false', 'Inactive')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class DatasetProjectAssignmentForm(forms.Form):
    """Form for assigning datasets to projects"""
    projects = forms.ModelMultipleChoiceField(
        queryset=None,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        }),
        help_text="Choose one or more projects to associate this dataset with",
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        dataset = kwargs.pop('dataset', None)
        super().__init__(*args, **kwargs)
        
        if user:
            # Show projects where user is owner or collaborator, or all projects if superuser
            from projects.models import Project
            if user.is_superuser:
                self.fields['projects'].queryset = Project.objects.all().order_by('title')
            else:
                self.fields['projects'].queryset = Project.objects.filter(
                    Q(owner=user) | Q(collaborators=user)
                ).distinct().order_by('title')
            
            # Pre-select current projects if editing
            if dataset and dataset.pk:
                self.fields['projects'].initial = dataset.projects.all()


class DatasetAnalysisForm(forms.ModelForm):
    """Form for uploading analysis/dataviz files"""
    
    class Meta:
        model = DatasetAnalysis
        fields = ['title', 'description', 'file']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Population Growth Analysis, Revenue Trends Visualization'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional: Describe your analysis or visualization...'
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.html,.png,.jpg,.jpeg,.svg,.csv,.xlsx,.xls,.json,.ipynb,.r,.py,.zip'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.dataset = kwargs.pop('dataset', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Add help text
        self.fields['title'].help_text = 'Give your analysis or visualization a descriptive title'
        self.fields['description'].help_text = 'Optional: Provide details about your analysis or visualization'
        self.fields['file'].help_text = 'Upload your analysis file (PDF, HTML, images, CSV, Excel, JSON, Jupyter notebooks, R scripts, Python scripts, ZIP, max 100MB)'
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Check file size (100MB limit)
            if file.size > 100 * 1024 * 1024:
                raise forms.ValidationError('File size exceeds the 100MB limit.')
            
            # Check file extension
            allowed_extensions = [
                '.pdf', '.html', '.png', '.jpg', '.jpeg', '.svg',
                '.csv', '.xlsx', '.xls', '.json', '.ipynb', '.r', '.py', '.zip'
            ]
            import os
            _, ext = os.path.splitext(file.name)
            if ext.lower() not in allowed_extensions:
                raise forms.ValidationError(
                    f'File type "{ext}" is not allowed. Allowed types: {", ".join(allowed_extensions)}'
                )
        return file
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.dataset:
            instance.dataset = self.dataset
        if self.user:
            instance.uploaded_by = self.user
        if instance.file:
            instance.file_size = instance.file.size
            instance.original_name = instance.file.name
        if commit:
            instance.save()
        return instance
